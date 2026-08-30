# Gateway Instrumentation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre visible l'activité gateway en ajoutant la latence et les signaux d'erreur dans les événements d'audit, puis exposer des stats agrégées (24h) via un endpoint admin et un widget dashboard.

**Architecture:** Aucun nouveau modèle ni nouvelle table. (1) `proxy_request()` dans `gateway/service.py` mesure la latence avec `time.monotonic()` et enrichit les métadonnées de l'audit `gateway.resource.accessed` avec `latency_ms`, `is_5xx`, `is_cf_refused`. Les exceptions upstream (ConnectError, Timeout) écrivent un second événement `gateway.request.failed`. (2) `GET /admin/gateway-stats` agrège ces événements en mémoire pour les 24 dernières heures. (3) Le dashboard admin affiche un widget avec ces stats.

**Tech Stack:** Python FastAPI, SQLAlchemy, Next.js React.

---

## Fichiers créés ou modifiés

| Fichier | Action | Responsabilité |
|---|---|---|
| `apps/api/app/modules/gateway/service.py` | Modify | Timing + métadonnées enrichies dans `proxy_request()` |
| `apps/api/app/modules/admin/router.py` | Modify | Ajouter `GET /admin/gateway-stats` |
| `apps/api/tests/integration/test_gateway.py` | Modify | Vérifier que l'audit contient `latency_ms` + test `gateway.request.failed` |
| `apps/api/tests/integration/test_admin_router.py` | Modify | Test `GET /admin/gateway-stats` |
| `apps/web/src/lib/api/server-admin.ts` | Modify | Type `GatewayStats` + méthode `gatewayStats()` |
| `apps/web/src/app/(admin)/admin/page.tsx` | Modify | Widget stats gateway dans le dashboard |

---

## Task 1: Enrichir l'audit gateway avec latence et signaux d'erreur

**Context:** `proxy_request()` dans `apps/api/app/modules/gateway/service.py` (lignes 98–139) fait l'appel httpx et écrit un audit `gateway.resource.accessed` avec `{"status_code": ..., "path": ...}`. Les exceptions `httpx.ConnectError` et `httpx.TimeoutException` lèvent une `UpstreamUnavailableException` (HTTP 502) sans écrire d'événement d'audit. Le module `time` (stdlib Python) est disponible sans installation.

**Files:**
- Modify: `apps/api/app/modules/gateway/service.py`
- Modify: `apps/api/tests/integration/test_gateway.py`

- [ ] **Step 1: Écrire les tests (failing)**

Ajouter à la fin de `apps/api/tests/integration/test_gateway.py` :

```python
@respx.mock
def test_gateway_audit_includes_latency_ms(client, db_session):
    """L'audit gateway.resource.accessed contient latency_ms, is_5xx, is_cf_refused."""
    _make_user(db_session)
    _make_session(db_session)
    _make_env(db_session)

    respx.get("https://upstream.cfargotunnel.com/").mock(
        return_value=httpx.Response(200, content=b"ok")
    )

    client.cookies.set("devgate_session", "s-gw")
    client.get("/gateway/env-gw/")

    event = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.event_type == "gateway.resource.accessed")
        .first()
    )
    assert event is not None
    assert "latency_ms" in event.metadata_json
    assert isinstance(event.metadata_json["latency_ms"], int)
    assert event.metadata_json["is_5xx"] is False
    assert event.metadata_json["is_cf_refused"] is False


@respx.mock
def test_gateway_audit_marks_5xx(client, db_session):
    """is_5xx=True quand l'upstream répond 500."""
    _make_user(db_session)
    _make_session(db_session)
    _make_env(db_session)

    respx.get("https://upstream.cfargotunnel.com/").mock(
        return_value=httpx.Response(500, content=b"error")
    )

    client.cookies.set("devgate_session", "s-gw")
    client.get("/gateway/env-gw/")

    event = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.event_type == "gateway.resource.accessed")
        .first()
    )
    assert event.metadata_json["is_5xx"] is True
    assert event.metadata_json["is_cf_refused"] is False


@respx.mock
def test_gateway_audit_marks_cf_refused(client, db_session):
    """is_cf_refused=True quand l'upstream répond 403."""
    _make_user(db_session)
    _make_session(db_session)
    _make_env(db_session)

    respx.get("https://upstream.cfargotunnel.com/").mock(
        return_value=httpx.Response(403, content=b"forbidden")
    )

    client.cookies.set("devgate_session", "s-gw")
    client.get("/gateway/env-gw/")

    event = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.event_type == "gateway.resource.accessed")
        .first()
    )
    assert event.metadata_json["is_cf_refused"] is True
    assert event.metadata_json["is_5xx"] is False


@respx.mock
def test_gateway_unavailable_creates_failed_audit_event(client, db_session):
    """ConnectError crée un événement gateway.request.failed."""
    _make_user(db_session)
    _make_session(db_session)
    _make_env(db_session)

    respx.get("https://upstream.cfargotunnel.com/").mock(
        side_effect=httpx.ConnectError("refused")
    )

    client.cookies.set("devgate_session", "s-gw")
    res = client.get("/gateway/env-gw/")
    assert res.status_code == 502

    event = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.event_type == "gateway.request.failed")
        .first()
    )
    assert event is not None
    assert event.metadata_json["reason"] == "upstream_unavailable"
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
cd apps/api && python -m pytest tests/integration/test_gateway.py::test_gateway_audit_includes_latency_ms tests/integration/test_gateway.py::test_gateway_unavailable_creates_failed_audit_event -v
```

Expected: FAIL — `latency_ms` absent de metadata_json, `gateway.request.failed` absent.

- [ ] **Step 3: Modifier `proxy_request()` dans `gateway/service.py`**

Remplacer le contenu intégral de `apps/api/app/modules/gateway/service.py` :

```python
"""
Gateway DevGate — couche explicite, pas un bricolage de controller.

Règles critiques :
- vérifie session ET grant avant de proxifier
- injecte les credentials Cloudflare Access service token
- ne renvoie jamais l'upstream_hostname ni le service_token au navigateur
- distingue : non autorisé / ressource introuvable / upstream KO
"""
import json
import logging
import time
from datetime import timezone

import httpx
from sqlalchemy.orm import Session as DbSession

from app.modules.audit.service import audit
from app.modules.secrets.store import SecretStore, SecretNotFoundError, SecretRevokedError

logger = logging.getLogger(__name__)
from app.shared.exceptions import (
    ForbiddenException, NotFoundException, UpstreamUnavailableException,
)
from app.shared.models import AccessGrant, Environment, Project, User


def resolve_environment(env_id: str, user: User, db: DbSession) -> Environment:
    """Vérifie que l'utilisateur a accès à l'environnement et retourne sa config."""
    env = db.query(Environment).filter(Environment.id == env_id).first()
    if not env:
        raise NotFoundException("Environnement introuvable")

    project = db.query(Project).filter(Project.id == env.project_id).first()
    if not project:
        raise NotFoundException()

    # Vérification du grant par client (v1 : par organisation)
    grant = (
        db.query(AccessGrant)
        .filter(
            AccessGrant.user_id == user.id,
            AccessGrant.organization_id == project.organization_id,
            AccessGrant.revoked_at.is_(None),
        )
        .first()
    )
    if not grant:
        raise ForbiddenException("Accès non autorisé à cet environnement")

    return env


def _get_service_token(token_ref: str, secret_store: SecretStore) -> tuple[str, str]:
    """Récupère les credentials CF Access depuis le SecretStore chiffré.

    Retourne ("", "") si le token est absent, révoqué ou illisible.
    Ne lève jamais d'exception — un token manquant doit résulter en un rejet CF, pas un crash.
    """
    try:
        payload = json.loads(secret_store.get(token_ref))
        return payload.get("client_id", ""), payload.get("client_secret", "")
    except (SecretNotFoundError, SecretRevokedError):
        return "", ""
    except Exception:
        logger.warning("Erreur inattendue lors de la lecture du service token %s", token_ref, exc_info=True)
        return "", ""


def get_upstream_proxy_headers(
    env: Environment,
    user_id: str,
    request_headers: dict,
    secret_store: SecretStore | None = None,
) -> dict:
    """Construit les headers à envoyer à l'upstream.

    - Retire les headers de session et de transport
    - Empêche le spoofing de X-DevGate-User côté client
    - Injecte les credentials CF Access via SecretStore si service_token_ref configuré
    """
    proxy_headers = {
        k: v for k, v in request_headers.items()
        if k.lower() not in ("host", "cookie", "accept-encoding", "x-devgate-user")
    }
    proxy_headers["Accept-Encoding"] = "identity"
    proxy_headers["X-DevGate-User"] = user_id

    if env.service_token_ref and secret_store is not None:
        cf_client_id, cf_client_secret = _get_service_token(env.service_token_ref, secret_store)
        if cf_client_id:
            proxy_headers["CF-Access-Client-Id"] = cf_client_id
        if cf_client_secret:
            proxy_headers["CF-Access-Client-Secret"] = cf_client_secret

    return proxy_headers


async def proxy_request(
    env: Environment,
    method: str,
    path: str,
    headers: dict,
    body: bytes | None,
    user: User,
    db: DbSession,
    secret_store: SecretStore | None = None,
) -> httpx.Response:
    """Proxifie la requête vers l'upstream Cloudflare protégé."""
    if not env.upstream_hostname:
        raise UpstreamUnavailableException("Upstream non configuré")

    upstream_url = f"https://{env.upstream_hostname}{path}"

    proxy_headers = get_upstream_proxy_headers(env, user.id, headers, secret_store)

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            response = await client.request(
                method=method,
                url=upstream_url,
                headers=proxy_headers,
                content=body,
            )
    except httpx.ConnectError as e:
        audit(
            db,
            actor_user_id=user.id,
            event_type="gateway.request.failed",
            target_type="environment",
            target_id=env.id,
            metadata={"reason": "upstream_unavailable", "detail": str(e)[:200]},
        )
        db.commit()
        raise UpstreamUnavailableException(f"Impossible de joindre l'upstream : {e}") from e
    except httpx.TimeoutException as e:
        audit(
            db,
            actor_user_id=user.id,
            event_type="gateway.request.failed",
            target_type="environment",
            target_id=env.id,
            metadata={"reason": "timeout"},
        )
        db.commit()
        raise UpstreamUnavailableException("L'upstream n'a pas répondu à temps") from e

    latency_ms = int((time.monotonic() - start) * 1000)

    audit(
        db,
        actor_user_id=user.id,
        event_type="gateway.resource.accessed",
        target_type="environment",
        target_id=env.id,
        metadata={
            "status_code": response.status_code,
            "path": path,
            "latency_ms": latency_ms,
            "is_5xx": response.status_code >= 500,
            "is_cf_refused": response.status_code == 403,
        },
    )
    db.commit()

    return response
```

- [ ] **Step 4: Vérifier que les tests passent**

```bash
cd apps/api && python -m pytest tests/integration/test_gateway.py -v
```

Expected: tous PASS.

- [ ] **Step 5: Suite complète**

```bash
cd apps/api && python -m pytest -q
```

Expected: tous PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/api/app/modules/gateway/service.py \
        apps/api/tests/integration/test_gateway.py
git commit -m "feat(gateway): audit enrichi — latency_ms, is_5xx, is_cf_refused, gateway.request.failed"
```

---

## Task 2: Endpoint `GET /admin/gateway-stats`

**Context:** `apps/api/app/modules/admin/router.py` expose les routes admin. L'import `AuditEvent` est déjà présent. `datetime` et `timezone` sont déjà importés. Le nouvel endpoint agrège en mémoire Python (pas de SQL GROUP BY complexe) les événements `gateway.resource.accessed` et `gateway.request.failed` des 24 dernières heures. Pour le p95 : `sorted(latencies)[int(len(latencies) * 0.95)]` — si moins de 20 items, p95 == max (comportement acceptable pour v1).

**Files:**
- Modify: `apps/api/app/modules/admin/router.py`
- Modify: `apps/api/tests/integration/test_admin_router.py`

- [ ] **Step 1: Écrire le test (failing)**

Ajouter à la fin de `apps/api/tests/integration/test_admin_router.py` :

```python
def test_gateway_stats_empty(client, db_session):
    """GET /admin/gateway-stats retourne des zéros quand aucun événement gateway."""
    _make_admin(db_session)
    _auth(client)

    r = client.get("/admin/gateway-stats")
    assert r.status_code == 200
    data = r.json()
    assert data["total_requests"] == 0
    assert data["errors_5xx"] == 0
    assert data["cf_refused"] == 0
    assert data["upstream_unavailable"] == 0
    assert data["avg_latency_ms"] is None
    assert data["p95_latency_ms"] is None
    assert data["since_hours"] == 24


def test_gateway_stats_counts_events(client, db_session):
    """GET /admin/gateway-stats agrège correctement les événements d'audit."""
    from datetime import datetime, timezone
    from app.shared.models import AuditEvent

    _make_admin(db_session)
    _auth(client)

    # 2 requêtes normales
    for i, lat in enumerate([100, 200]):
        db_session.add(AuditEvent(
            id=f"gw-ok-{i}",
            event_type="gateway.resource.accessed",
            actor_user_id="admin-1",
            target_type="environment",
            target_id="env-x",
            metadata_json={"status_code": 200, "path": "/", "latency_ms": lat, "is_5xx": False, "is_cf_refused": False},
        ))
    # 1 erreur 5xx
    db_session.add(AuditEvent(
        id="gw-5xx",
        event_type="gateway.resource.accessed",
        actor_user_id="admin-1",
        target_type="environment",
        target_id="env-x",
        metadata_json={"status_code": 500, "path": "/", "latency_ms": 50, "is_5xx": True, "is_cf_refused": False},
    ))
    # 1 refus CF
    db_session.add(AuditEvent(
        id="gw-cf",
        event_type="gateway.resource.accessed",
        actor_user_id="admin-1",
        target_type="environment",
        target_id="env-x",
        metadata_json={"status_code": 403, "path": "/", "latency_ms": 30, "is_5xx": False, "is_cf_refused": True},
    ))
    # 1 upstream indisponible
    db_session.add(AuditEvent(
        id="gw-fail",
        event_type="gateway.request.failed",
        actor_user_id="admin-1",
        target_type="environment",
        target_id="env-x",
        metadata_json={"reason": "upstream_unavailable"},
    ))
    db_session.commit()

    r = client.get("/admin/gateway-stats")
    assert r.status_code == 200
    data = r.json()
    assert data["total_requests"] == 4  # 3 accessed + 1 failed sur 5xx/cf n'est pas "failed"
    assert data["errors_5xx"] == 1
    assert data["cf_refused"] == 1
    assert data["upstream_unavailable"] == 1
    # avg_latency_ms = (100+200+50+30) / 4 = 95
    assert data["avg_latency_ms"] == 95
```

Wait — le test ci-dessus compte les `gateway.resource.accessed` pour `total_requests`. Il faut décider : est-ce que `total_requests` = uniquement les `resource.accessed`, ou `resource.accessed` + `request.failed` ? Pour l'interprétation "toutes les tentatives", je vais inclure les deux dans `total_requests`. Corrigeons :

```python
def test_gateway_stats_counts_events(client, db_session):
    """GET /admin/gateway-stats agrège correctement les événements d'audit."""
    from app.shared.models import AuditEvent

    _make_admin(db_session)
    _auth(client)

    # 2 requêtes normales (accessed)
    for i, lat in enumerate([100, 200]):
        db_session.add(AuditEvent(
            id=f"gw-ok-{i}",
            event_type="gateway.resource.accessed",
            metadata_json={"status_code": 200, "path": "/", "latency_ms": lat, "is_5xx": False, "is_cf_refused": False},
        ))
    # 1 erreur 5xx (accessed)
    db_session.add(AuditEvent(
        id="gw-5xx",
        event_type="gateway.resource.accessed",
        metadata_json={"status_code": 500, "path": "/", "latency_ms": 50, "is_5xx": True, "is_cf_refused": False},
    ))
    # 1 refus CF (accessed)
    db_session.add(AuditEvent(
        id="gw-cf",
        event_type="gateway.resource.accessed",
        metadata_json={"status_code": 403, "path": "/", "latency_ms": 30, "is_5xx": False, "is_cf_refused": True},
    ))
    # 1 upstream indisponible (failed)
    db_session.add(AuditEvent(
        id="gw-fail",
        event_type="gateway.request.failed",
        metadata_json={"reason": "upstream_unavailable"},
    ))
    db_session.commit()

    r = client.get("/admin/gateway-stats")
    assert r.status_code == 200
    data = r.json()
    assert data["total_requests"] == 4  # 4 accessed (including failed ones)
    assert data["errors_5xx"] == 1
    assert data["cf_refused"] == 1
    assert data["upstream_unavailable"] == 1
    # latencies from accessed events: [100, 200, 50, 30] → avg = 95
    assert data["avg_latency_ms"] == 95
```

- [ ] **Step 2: Vérifier que le test échoue**

```bash
cd apps/api && python -m pytest tests/integration/test_admin_router.py::test_gateway_stats_empty tests/integration/test_admin_router.py::test_gateway_stats_counts_events -v
```

Expected: `404 Not Found` ou FAIL.

- [ ] **Step 3: Ajouter l'endpoint dans `router.py`**

Ajouter à la fin de `apps/api/app/modules/admin/router.py` (avant la dernière ligne du fichier) :

```python
# ── Gateway stats ─────────────────────────────────────────────────

@router.get("/gateway-stats")
def get_gateway_stats(db: DbSession = Depends(get_db)):
    """Stats des requêtes gateway sur les 24 dernières heures.

    Agrège les événements d'audit pour éviter un modèle supplémentaire.
    Acceptable pour v1 (volume faible). Ne filtre pas par environnement.
    """
    from datetime import timedelta
    since = datetime.now(tz=timezone.utc) - timedelta(hours=24)

    accessed = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.event_type == "gateway.resource.accessed",
            AuditEvent.created_at >= since,
        )
        .all()
    )

    upstream_unavailable = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.event_type == "gateway.request.failed",
            AuditEvent.created_at >= since,
        )
        .count()
    )

    total = len(accessed) + upstream_unavailable
    errors_5xx = sum(1 for e in accessed if e.metadata_json and e.metadata_json.get("is_5xx"))
    cf_refused = sum(1 for e in accessed if e.metadata_json and e.metadata_json.get("is_cf_refused"))
    latencies = [
        e.metadata_json["latency_ms"]
        for e in accessed
        if e.metadata_json and isinstance(e.metadata_json.get("latency_ms"), int)
    ]

    avg_latency_ms: int | None = None
    p95_latency_ms: int | None = None
    if latencies:
        avg_latency_ms = int(sum(latencies) / len(latencies))
        sorted_latencies = sorted(latencies)
        p95_idx = max(0, int(len(sorted_latencies) * 0.95) - 1)
        p95_latency_ms = sorted_latencies[p95_idx]

    return {
        "since_hours": 24,
        "total_requests": total,
        "errors_5xx": errors_5xx,
        "cf_refused": cf_refused,
        "upstream_unavailable": upstream_unavailable,
        "avg_latency_ms": avg_latency_ms,
        "p95_latency_ms": p95_latency_ms,
    }
```

- [ ] **Step 4: Vérifier que les tests passent**

```bash
cd apps/api && python -m pytest tests/integration/test_admin_router.py -v
```

Expected: tous PASS.

- [ ] **Step 5: Suite complète**

```bash
cd apps/api && python -m pytest -q
```

Expected: tous PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/api/app/modules/admin/router.py \
        apps/api/tests/integration/test_admin_router.py
git commit -m "feat(admin): GET /admin/gateway-stats — agrégat 24h depuis audit events"
```

---

## Task 3: Widget gateway stats dans le dashboard admin

**Context:** `apps/web/src/app/(admin)/admin/page.tsx` est un Server Component qui charge `stats` et `events` via `serverAdminApi`. Le type `StatsResponse` et les méthodes `serverAdminApi.stats()` / `serverAdminApi.auditEvents()` sont dans `server-admin.ts`. Le dashboard affiche une `statsGrid` avec 4 cartes (clients, envs, users, events today) puis un tableau d'activité récente. On ajoute un second bloc de cartes sous le premier.

**Files:**
- Modify: `apps/web/src/lib/api/server-admin.ts`
- Modify: `apps/web/src/app/(admin)/admin/page.tsx`

- [ ] **Step 1: Ajouter `GatewayStats` et `gatewayStats()` dans `server-admin.ts`**

Dans `apps/web/src/lib/api/server-admin.ts`, ajouter après le type `StatsResponse` :

```typescript
export type GatewayStats = {
  since_hours: number;
  total_requests: number;
  errors_5xx: number;
  cf_refused: number;
  upstream_unavailable: number;
  avg_latency_ms: number | null;
  p95_latency_ms: number | null;
};
```

Et dans l'objet `serverAdminApi`, ajouter après `auditEvents` :

```typescript
  gatewayStats: () => adminRequest<GatewayStats>("/admin/gateway-stats"),
```

- [ ] **Step 2: Mettre à jour `admin/page.tsx`**

Remplacer le contenu intégral de `apps/web/src/app/(admin)/admin/page.tsx` :

```tsx
// Back-office — Dashboard
// Référence visuelle : docs/ds/mockups/devgate-backoffice.mockup.html
import { redirect } from "next/navigation";
import {
  serverAdminApi,
  AdminApiError,
  type StatsResponse,
  type AdminAuditEvent,
  type GatewayStats,
} from "@/lib/api/server-admin";
import styles from "./admin.module.css";

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("fr-FR", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default async function AdminDashboardPage() {
  let stats: StatsResponse;
  let events: AdminAuditEvent[];
  let gatewayStats: GatewayStats;

  try {
    [stats, events, gatewayStats] = await Promise.all([
      serverAdminApi.stats(),
      serverAdminApi.auditEvents(10),
      serverAdminApi.gatewayStats(),
    ]);
  } catch (err) {
    if (err instanceof AdminApiError && err.status === 401) redirect("/login");
    if (err instanceof AdminApiError && err.status === 403) redirect("/access-denied");
    redirect("/session-expired");
  }

  const STATS = [
    { label: "Clients actifs", value: stats.active_orgs },
    { label: "Environnements", value: stats.active_envs },
    { label: "Utilisateurs", value: stats.active_users },
    { label: "Événements aujourd'hui", value: stats.events_today },
  ];

  const GATEWAY_STATS = [
    { label: "Requêtes (24h)", value: gatewayStats.total_requests },
    { label: "Erreurs 5xx", value: gatewayStats.errors_5xx },
    { label: "Refus CF Access", value: gatewayStats.cf_refused },
    { label: "Upstream indispo", value: gatewayStats.upstream_unavailable },
    {
      label: "Latence moy.",
      value: gatewayStats.avg_latency_ms !== null ? `${gatewayStats.avg_latency_ms}ms` : "—",
    },
    {
      label: "Latence p95",
      value: gatewayStats.p95_latency_ms !== null ? `${gatewayStats.p95_latency_ms}ms` : "—",
    },
  ];

  return (
    <div className={styles.page}>
      <h1 className={styles.pageTitle}>Dashboard</h1>
      <p className={styles.pageSub}>Vue d&apos;ensemble de l&apos;activité DevGate</p>

      <div className={styles.statsGrid}>
        {STATS.map((s) => (
          <div key={s.label} className={styles.statCard}>
            <div className={styles.statLabel}>{s.label}</div>
            <div className={styles.statValue}>{s.value}</div>
          </div>
        ))}
      </div>

      <div className={styles.sectionTitle} style={{ marginTop: "28px", marginBottom: "12px" }}>
        Gateway — 24 dernières heures
      </div>
      <div className={styles.statsGrid}>
        {GATEWAY_STATS.map((s) => (
          <div key={s.label} className={styles.statCard}>
            <div className={styles.statLabel}>{s.label}</div>
            <div className={styles.statValue}>{s.value}</div>
          </div>
        ))}
      </div>

      <div className={styles.sectionTitle} style={{ marginTop: "28px" }}>Activité récente</div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Date</th>
            <th>Événement</th>
            <th>Acteur</th>
            <th>Cible</th>
          </tr>
        </thead>
        <tbody>
          {events.length === 0 ? (
            <tr className={styles.emptyRow}>
              <td colSpan={4}>Aucun événement enregistré</td>
            </tr>
          ) : (
            events.map((e) => (
              <tr key={e.id}>
                <td>{formatDate(e.created_at)}</td>
                <td>
                  <span className={styles.eventType}>{e.event_type}</span>
                </td>
                <td>{e.actor_user_id ?? "—"}</td>
                <td>{e.target_id ?? "—"}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/web/src/lib/api/server-admin.ts \
        apps/web/src/app/(admin)/admin/page.tsx
git commit -m "feat(admin): widget stats gateway 24h dans le dashboard"
```

---

## Self-Review

### Spec coverage
- ✅ "temps de réponse gateway" — `latency_ms` dans audit + `avg_latency_ms` / `p95_latency_ms` dans stats
- ✅ "erreurs 5xx" — `is_5xx` dans audit + `errors_5xx` dans stats
- ✅ "refus upstream Access" — `is_cf_refused` (403) dans audit + `cf_refused` dans stats
- ✅ "ressource indisponible" — `gateway.request.failed` + `upstream_unavailable` dans stats
- ✅ "logs suffisants pour debugger une panne simple" (Build plan Phase 6 livrables)

### Placeholder scan
Aucun placeholder détecté. Tous les steps contiennent le code complet.

### Type consistency
- `GatewayStats` défini dans Task 3 Step 1 — tous les champs correspondent à la réponse de `get_gateway_stats()` définie en Task 2 Step 3
- `total_requests` = `gateway.resource.accessed` + `gateway.request.failed` — cohérent entre l'implémentation et le test
- `latency_ms: int` dans audit metadata — cohérent avec `isinstance(..., int)` dans le filtre de Task 2 Step 3

### Points hors-scope (YAGNI)
- Modèle dédié pour les métriques gateway — hors v1
- Alerting sur seuils — hors v1
- Breakdown par environnement dans les stats — hors v1
- Filtrage par fenêtre temporelle personnalisable — hors v1
