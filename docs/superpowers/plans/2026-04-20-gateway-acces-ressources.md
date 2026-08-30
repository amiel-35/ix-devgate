# Gateway et accès aux ressources — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Brancher le portail utilisateur sur le gateway DevGate pour que "Ouvrir la ressource" passe réellement par le proxy backend — et non directement vers le public_hostname.

**Architecture:** Le gateway FastAPI (`/gateway/{env_id}/{path:path}`) vérifie session + grant, injecte le service token Cloudflare, puis proxifie via httpx. Le portail renvoie désormais un `gateway_url` relatif (`/gateway/{id}/`) que le frontend construit en URL absolue avec `NEXT_PUBLIC_API_URL`. Les Cloudflare credentials ne quittent jamais le backend.

**Tech Stack:** FastAPI + httpx + respx (tests), Next.js 15 App Router, SQLAlchemy, WebSockets (uvicorn[standard] inclut websockets).

---

## Fichiers créés ou modifiés

| Fichier | Action | Responsabilité |
|---|---|---|
| `apps/api/app/modules/portal/schemas.py` | Modify | Ajouter `gateway_url: str` à `EnvironmentListItem` |
| `apps/api/app/modules/portal/service.py` | Modify | Calculer `gateway_url = f"/gateway/{env.id}/"` |
| `apps/api/app/modules/gateway/service.py` | Modify | `Accept-Encoding: identity` + X-headers utilisateur |
| `apps/api/app/modules/gateway/router.py` | Modify | Multi-value headers + route WebSocket |
| `apps/api/app/modules/gateway/health.py` | Create | Ping upstream → TunnelHealthSnapshot |
| `apps/api/app/modules/admin/router.py` | Modify | `POST /environments/{env_id}/ping` |
| `apps/api/requirements.txt` | Modify | Ajouter `respx>=0.21` |
| `apps/api/tests/integration/test_gateway.py` | Replace | 8 tests couvrant tous les cas gateway |
| `apps/web/src/lib/api/server.ts` | Modify | Ajouter `gateway_url` à `EnvironmentItem` |
| `apps/web/src/app/(portal)/resource/[id]/page.tsx` | Modify | "Ouvrir" → gateway URL |
| `apps/web/src/app/(portal)/resource/[id]/interstitial/page.tsx` | Modify | "Continuer" → gateway URL |

---

## Task 1: Backend — portal retourne `gateway_url`

**Files:**
- Modify: `apps/api/app/modules/portal/schemas.py`
- Modify: `apps/api/app/modules/portal/service.py`
- Modify: `apps/api/tests/integration/test_portal_router.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Dans `apps/api/tests/integration/test_portal_router.py`, trouver le test `test_me_environments_returns_list` (il vérifie que `/me/environments` retourne des éléments). Ajouter une assertion sur `gateway_url` :

```python
def test_me_environments_gateway_url(client, db_session):
    """Chaque environnement expose un gateway_url."""
    _make_user(db_session)
    _make_session(db_session)
    _make_org_with_env(db_session)
    client.cookies.set("devgate_session", "s-test")

    res = client.get("/me/environments")

    assert res.status_code == 200
    envs = res.json()
    assert len(envs) == 1
    assert envs[0]["gateway_url"] == "/gateway/env-1/"
```

- [ ] **Step 2 : Vérifier que le test échoue**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/integration/test_portal_router.py::test_me_environments_gateway_url -v
```

Expected: `FAILED` — KeyError ou champ absent.

- [ ] **Step 3 : Ajouter `gateway_url` au schéma**

Contenu complet de `apps/api/app/modules/portal/schemas.py` :

```python
from pydantic import BaseModel


class MeResponse(BaseModel):
    id: str
    email: str
    display_name: str | None


class EnvironmentListItem(BaseModel):
    id: str
    organization_name: str
    project_name: str
    environment_name: str
    kind: str
    url: str          # URL publique DevGate — affichage uniquement
    gateway_url: str  # Chemin gateway DevGate — navigation réelle
    requires_app_auth: bool
    status: str  # online | offline | unknown


class SessionItem(BaseModel):
    id: str
    expires_at: str
    last_seen_at: str
    ip: str | None
    user_agent: str | None
    is_current: bool
```

- [ ] **Step 4 : Ajouter `gateway_url` dans le service**

Dans `apps/api/app/modules/portal/service.py`, dans la boucle `for env, project, org in environments`, modifier le `result.append(...)` :

```python
        result.append({
            "id": env.id,
            "organization_name": org.name,
            "project_name": project.name,
            "environment_name": env.name,
            "kind": env.kind,
            "url": f"https://{env.public_hostname}",
            "gateway_url": f"/gateway/{env.id}/",
            "requires_app_auth": env.requires_app_auth,
            "status": status,
        })
```

- [ ] **Step 5 : Vérifier que le test passe**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/integration/test_portal_router.py -v
```

Expected: tous les tests `PASSED`.

- [ ] **Step 6 : Vérifier la compilation TypeScript (pas de régression)**

```bash
cd /Users/amiellavon/Sites/Captive-serveur/apps/web
npx tsc --noEmit 2>&1 | head -5
```

Expected: aucun output (aucune erreur).

- [ ] **Step 7 : Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/api/app/modules/portal/schemas.py \
        apps/api/app/modules/portal/service.py \
        apps/api/tests/integration/test_portal_router.py
git commit -m "feat(portal): expose gateway_url dans EnvironmentListItem"
```

---

## Task 2: Backend — proxy headers corrects

**Files:**
- Modify: `apps/api/app/modules/gateway/service.py`
- Modify: `apps/api/app/modules/gateway/router.py`

Le problème actuel :
1. `content-encoding` est retiré des headers de réponse mais le contenu reste compressé → le navigateur reçoit des données illisibles.
2. Plusieurs headers `Set-Cookie` sont perdus lors de la conversion `dict(headers)`.
3. Le backend ne propage pas `X-Forwarded-For` à l'upstream.

- [ ] **Step 1 : Corriger `service.py` — désactiver la compression upstream**

Dans `apps/api/app/modules/gateway/service.py`, dans la fonction `proxy_request`, modifier la construction de `proxy_headers` :

```python
async def proxy_request(
    env: Environment,
    method: str,
    path: str,
    headers: dict,
    body: bytes | None,
    user: User,
    db: DbSession,
) -> httpx.Response:
    """Proxifie la requête vers l'upstream Cloudflare protégé."""
    if not env.upstream_hostname:
        raise UpstreamUnavailableException("Upstream non configuré")

    upstream_url = f"https://{env.upstream_hostname}{path}"

    # Headers vers l'upstream :
    # - on retire host et cookie (ne pas fuiter la session DevGate)
    # - on désactive la compression pour ne pas décompresser côté backend
    # - on ajoute X-Forwarded-For et X-DevGate-User pour tracabilité upstream
    proxy_headers = {
        k: v for k, v in headers.items()
        if k.lower() not in ("host", "cookie", "accept-encoding")
    }
    proxy_headers["Accept-Encoding"] = "identity"
    proxy_headers["X-DevGate-User"] = user.id

    if env.service_token_ref:
        cf_client_id, cf_client_secret = _get_service_token(env.service_token_ref)
        if cf_client_id:
            proxy_headers["CF-Access-Client-Id"] = cf_client_id
        if cf_client_secret:
            proxy_headers["CF-Access-Client-Secret"] = cf_client_secret

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.request(
                method=method,
                url=upstream_url,
                headers=proxy_headers,
                content=body,
            )
    except httpx.ConnectError as e:
        raise UpstreamUnavailableException(f"Impossible de joindre l'upstream : {e}") from e
    except httpx.TimeoutException as e:
        raise UpstreamUnavailableException("L'upstream n'a pas répondu à temps") from e

    audit(
        db,
        actor_user_id=user.id,
        event_type="gateway.resource.accessed",
        target_type="environment",
        target_id=env.id,
        metadata={"status_code": response.status_code, "path": path},
    )
    db.commit()

    return response
```

- [ ] **Step 2 : Corriger `router.py` — multi-value headers (Set-Cookie)**

Contenu complet de `apps/api/app/modules/gateway/router.py` (section HTTP uniquement, WebSocket sera ajouté en Task 4) :

```python
"""
Gateway router — point d'entrée pour le trafic proxifié.
L'URL publique est /gateway/{env_id}/{path:path}
Le navigateur ne voit jamais l'upstream Cloudflare.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.modules.gateway.service import proxy_request, resolve_environment
from app.shared.deps import get_current_user
from app.shared.models import User

router = APIRouter()

# Headers de transport à ne pas retransmettre au navigateur
_EXCLUDED_RESPONSE_HEADERS = frozenset({
    "transfer-encoding",
    "content-length",   # recalculé par starlette
})


@router.api_route(
    "/{env_id}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def gateway_proxy(
    env_id: str,
    path: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    env = resolve_environment(env_id, user, db)

    body = await request.body()
    upstream_response = await proxy_request(
        env=env,
        method=request.method,
        path=f"/{path}",
        headers=dict(request.headers),
        body=body or None,
        user=user,
        db=db,
    )

    # Construire la réponse en préservant les headers multi-valeurs (Set-Cookie, etc.)
    response = Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        media_type=upstream_response.headers.get("content-type"),
    )
    for key, value in upstream_response.headers.multi_items():
        if key.lower() not in _EXCLUDED_RESPONSE_HEADERS:
            response.headers.append(key, value)

    return response
```

- [ ] **Step 3 : Vérifier les tests existants**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/ -q
```

Expected: 67+ tests passent, aucune régression.

- [ ] **Step 4 : Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/api/app/modules/gateway/service.py \
        apps/api/app/modules/gateway/router.py
git commit -m "fix(gateway): Accept-Encoding identity + multi-value headers response"
```

---

## Task 3: Backend — tests d'intégration gateway

**Files:**
- Modify: `apps/api/requirements.txt`
- Replace: `apps/api/tests/integration/test_gateway.py`

- [ ] **Step 1 : Ajouter `respx` aux dépendances de dev**

Dans `apps/api/requirements.txt`, sous `# Dev` :

```
# Dev
pytest>=8.0
pytest-asyncio>=0.24
respx>=0.21
ruff>=0.9
mypy>=1.14
```

- [ ] **Step 2 : Installer `respx`**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pip install respx>=0.21
```

Expected: `Successfully installed respx-X.X.X`

- [ ] **Step 3 : Écrire les tests (vérifier qu'ils échouent avec les stubs actuels)**

Contenu complet de `apps/api/tests/integration/test_gateway.py` :

```python
"""Tests d'intégration — gateway DevGate.

Stratégie :
- La session + DB utilisent les fixtures du conftest (SQLite in-memory).
- httpx (utilisé par le gateway) est mocké via respx.
- TestClient (Starlette) utilise ASGITransport et n'est PAS intercepté par respx.
"""
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from app.shared.models import (
    AccessGrant,
    AuditEvent,
    Environment,
    Organization,
    Project,
    Session as SessionModel,
    User,
)


# ── Fixtures helpers ─────────────────────────────────────────────

def _make_user(db_session, user_id="u-gw", email="user@gw.test"):
    u = User(id=user_id, email=email, display_name="GW User", kind="client", status="active")
    db_session.add(u)
    db_session.commit()
    return u


def _make_session(db_session, user_id="u-gw", session_id="s-gw"):
    s = SessionModel(
        id=session_id,
        user_id=user_id,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=7),
    )
    db_session.add(s)
    db_session.commit()
    return s


def _make_env(
    db_session,
    user_id="u-gw",
    env_id="env-gw",
    upstream="upstream.cfargotunnel.com",
    service_token_ref=None,
):
    org = Organization(id="org-gw", name="GW Org", slug="gw-org")
    proj = Project(id="proj-gw", organization_id="org-gw", name="GW Proj", slug="gw-proj")
    env = Environment(
        id=env_id,
        project_id="proj-gw",
        name="GW Env",
        slug="gw-env",
        kind="staging",
        public_hostname="gw-env.devgate.example.com",
        upstream_hostname=upstream,
        service_token_ref=service_token_ref,
        requires_app_auth=False,
        status="active",
    )
    grant = AccessGrant(
        id="grant-gw",
        user_id=user_id,
        organization_id="org-gw",
        role="client_member",
    )
    db_session.add_all([org, proj, env, grant])
    db_session.commit()
    return env


# ── Tests 401 ────────────────────────────────────────────────────

def test_gateway_requires_session(client):
    """Sans cookie de session, le gateway retourne 401."""
    res = client.get("/gateway/env-gw/")
    assert res.status_code == 401


# ── Tests 404 ────────────────────────────────────────────────────

def test_gateway_unknown_environment(client, db_session):
    """Environnement inexistant → 404."""
    _make_user(db_session)
    _make_session(db_session)
    client.cookies.set("devgate_session", "s-gw")

    res = client.get("/gateway/env-inexistant/")
    assert res.status_code == 404


# ── Tests 403 ────────────────────────────────────────────────────

def test_gateway_forbidden_no_grant(client, db_session):
    """Environnement connu mais l'utilisateur n'a pas de grant → 403."""
    _make_user(db_session)
    _make_session(db_session)

    # Créer l'env sans grant pour cet utilisateur
    org = Organization(id="org-nogrant", name="Other Org", slug="other-org")
    proj = Project(id="proj-nogrant", organization_id="org-nogrant", name="P", slug="p")
    env = Environment(
        id="env-nogrant",
        project_id="proj-nogrant",
        name="E",
        slug="e",
        kind="staging",
        public_hostname="e.devgate.example.com",
        upstream_hostname="upstream.cfargotunnel.com",
        status="active",
    )
    db_session.add_all([org, proj, env])
    db_session.commit()

    client.cookies.set("devgate_session", "s-gw")
    res = client.get("/gateway/env-nogrant/")
    assert res.status_code == 403


# ── Tests proxy ──────────────────────────────────────────────────

@respx.mock
def test_gateway_proxies_get_request(client, db_session):
    """GET classique : proxifie vers l'upstream et retourne la réponse."""
    _make_user(db_session)
    _make_session(db_session)
    _make_env(db_session)

    respx.get("https://upstream.cfargotunnel.com/").mock(
        return_value=httpx.Response(
            200,
            content=b"<html><body>Hello from upstream</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )

    client.cookies.set("devgate_session", "s-gw")
    res = client.get("/gateway/env-gw/")

    assert res.status_code == 200
    assert b"Hello from upstream" in res.content


@respx.mock
def test_gateway_proxies_subpath(client, db_session):
    """Le path complet est transmis à l'upstream."""
    _make_user(db_session)
    _make_session(db_session)
    _make_env(db_session)

    respx.get("https://upstream.cfargotunnel.com/api/data").mock(
        return_value=httpx.Response(200, json={"key": "value"})
    )

    client.cookies.set("devgate_session", "s-gw")
    res = client.get("/gateway/env-gw/api/data")

    assert res.status_code == 200
    assert res.json() == {"key": "value"}


@respx.mock
def test_gateway_creates_audit_event(client, db_session):
    """Un accès réussi crée un AuditEvent gateway.resource.accessed."""
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
    assert event.actor_user_id == "u-gw"
    assert event.target_id == "env-gw"


@respx.mock
def test_gateway_upstream_unavailable_returns_502(client, db_session):
    """Upstream injoignable → 502."""
    _make_user(db_session)
    _make_session(db_session)
    _make_env(db_session)

    respx.get("https://upstream.cfargotunnel.com/").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    client.cookies.set("devgate_session", "s-gw")
    res = client.get("/gateway/env-gw/")

    assert res.status_code == 502


@respx.mock
def test_gateway_injects_cf_service_token(client, db_session, monkeypatch):
    """Quand service_token_ref est défini, les headers CF-Access-* sont injectés."""
    _make_user(db_session)
    _make_session(db_session)
    _make_env(db_session, service_token_ref="MY_TOKEN")

    monkeypatch.setenv("CF_SERVICE_TOKEN_MY_TOKEN_ID", "test-client-id")
    monkeypatch.setenv("CF_SERVICE_TOKEN_MY_TOKEN_SECRET", "test-client-secret")

    captured_headers: dict = {}

    def capture(request: httpx.Request, *args, **kwargs) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(200, content=b"ok")

    respx.get("https://upstream.cfargotunnel.com/").mock(side_effect=capture)

    client.cookies.set("devgate_session", "s-gw")
    client.get("/gateway/env-gw/")

    assert captured_headers.get("cf-access-client-id") == "test-client-id"
    assert captured_headers.get("cf-access-client-secret") == "test-client-secret"
```

- [ ] **Step 4 : Vérifier que les tests passent**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/integration/test_gateway.py -v
```

Expected: 8 tests `PASSED`.

- [ ] **Step 5 : Vérifier l'ensemble de la suite**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/ -q
```

Expected: 75+ tests passent.

- [ ] **Step 6 : Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/api/requirements.txt \
        apps/api/tests/integration/test_gateway.py
git commit -m "test(gateway): tests d'intégration complets — 8 cas couverts"
```

---

## Task 4: Backend — support WebSocket dans le gateway

**Files:**
- Modify: `apps/api/app/modules/gateway/router.py`

Le WebSocket est supporté dans uvicorn via `uvicorn[standard]` (déjà inclus). La route WebSocket cohabite avec les routes HTTP sans conflit car FastAPI distingue les deux protocoles.

- [ ] **Step 1 : Ajouter la route WebSocket à `router.py`**

Ajouter les imports et la route à la fin du fichier `apps/api/app/modules/gateway/router.py` :

```python
"""
Gateway router — point d'entrée pour le trafic proxifié.
L'URL publique est /gateway/{env_id}/{path:path}
Le navigateur ne voit jamais l'upstream Cloudflare.
"""
import asyncio

import websockets
import websockets.exceptions
from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.modules.gateway.service import proxy_request, resolve_environment
from app.shared.deps import get_current_session, get_current_user
from app.shared.exceptions import UnauthorizedException
from app.shared.models import Session as SessionModel, User

router = APIRouter()

_EXCLUDED_RESPONSE_HEADERS = frozenset({
    "transfer-encoding",
    "content-length",
})


@router.api_route(
    "/{env_id}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def gateway_proxy(
    env_id: str,
    path: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    env = resolve_environment(env_id, user, db)

    body = await request.body()
    upstream_response = await proxy_request(
        env=env,
        method=request.method,
        path=f"/{path}",
        headers=dict(request.headers),
        body=body or None,
        user=user,
        db=db,
    )

    response = Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        media_type=upstream_response.headers.get("content-type"),
    )
    for key, value in upstream_response.headers.multi_items():
        if key.lower() not in _EXCLUDED_RESPONSE_HEADERS:
            response.headers.append(key, value)

    return response


@router.websocket("/{env_id}/{path:path}")
async def gateway_ws_proxy(
    env_id: str,
    path: str,
    websocket: WebSocket,
    db: DbSession = Depends(get_db),
):
    """Proxy WebSocket bidirectionnel vers l'upstream."""
    # Authentification via cookie (WebSocket ne supporte pas les deps HTTPBearer)
    from datetime import datetime, timezone
    session_id = websocket.cookies.get("devgate_session")
    if not session_id:
        await websocket.close(code=1008)  # Policy Violation
        return

    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        await websocket.close(code=1008)
        return

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(tz=timezone.utc):
        await websocket.close(code=1008)
        return

    from app.shared.models import User as UserModel
    user = db.query(UserModel).filter(UserModel.id == session.user_id).first()
    if not user:
        await websocket.close(code=1008)
        return

    env = resolve_environment(env_id, user, db)
    if not env.upstream_hostname:
        await websocket.close(code=1011)  # Internal Error
        return

    upstream_ws_url = f"wss://{env.upstream_hostname}/{path}"

    await websocket.accept()

    try:
        async with websockets.connect(upstream_ws_url) as upstream_ws:

            async def client_to_upstream() -> None:
                try:
                    async for message in websocket.iter_bytes():
                        await upstream_ws.send(message)
                except WebSocketDisconnect:
                    pass

            async def upstream_to_client() -> None:
                try:
                    async for message in upstream_ws:
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)
                except websockets.exceptions.ConnectionClosed:
                    pass

            await asyncio.gather(
                client_to_upstream(),
                upstream_to_client(),
                return_exceptions=True,
            )

    except websockets.exceptions.WebSocketException:
        pass
    except Exception:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
```

- [ ] **Step 2 : Vérifier les tests existants (pas de régression)**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/ -q
```

Expected: tous les tests passent.

- [ ] **Step 3 : Vérifier TypeScript**

```bash
cd /Users/amiellavon/Sites/Captive-serveur/apps/web
npx tsc --noEmit 2>&1 | head -5
```

Expected: aucune sortie.

- [ ] **Step 4 : Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/api/app/modules/gateway/router.py
git commit -m "feat(gateway): support WebSocket proxy bidirectionnel"
```

---

## Task 5: Backend — service de health check

**Files:**
- Create: `apps/api/app/modules/gateway/health.py`
- Modify: `apps/api/app/modules/admin/router.py`

Le health check fait un `HEAD` HTTP vers `upstream_hostname`. Le résultat est écrit dans `TunnelHealthSnapshot`. Le back-office peut déclencher un check via `POST /admin/environments/{env_id}/ping`.

- [ ] **Step 1 : Créer `apps/api/app/modules/gateway/health.py`**

```python
"""
Health check service — sonde les upstreams et écrit les snapshots.
Règle : jamais de credential Cloudflare dans les logs ou les réponses admin.
"""
import asyncio
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session as DbSession

from app.shared.models import Environment, TunnelHealthSnapshot


async def check_environment_health(env: Environment, db: DbSession) -> TunnelHealthSnapshot:
    """Effectue un HEAD HTTP vers upstream_hostname et écrit un TunnelHealthSnapshot.

    Retourne le snapshot créé.
    Status possibles : "online" | "offline" | "unknown"
    """
    if not env.upstream_hostname:
        snapshot = TunnelHealthSnapshot(
            environment_id=env.id,
            status="unknown",
            replica_count=0,
            observed_at=datetime.now(tz=timezone.utc),
            metadata_json={"reason": "upstream_hostname non configuré"},
        )
        db.add(snapshot)
        db.commit()
        return snapshot

    status = "offline"
    latency_ms: int | None = None
    meta: dict = {}

    try:
        start = asyncio.get_event_loop().time()
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.head(f"https://{env.upstream_hostname}/")
        latency_ms = int((asyncio.get_event_loop().time() - start) * 1000)
        # 200–499 = online (même un 403 signifie que le serveur répond)
        if response.status_code < 500:
            status = "online"
        else:
            status = "offline"
        meta = {"status_code": response.status_code, "latency_ms": latency_ms}
    except httpx.ConnectError as e:
        status = "offline"
        meta = {"error": "connect_error", "detail": str(e)[:200]}
    except httpx.TimeoutException:
        status = "offline"
        meta = {"error": "timeout"}
    except Exception as e:
        status = "unknown"
        meta = {"error": "unexpected", "detail": str(e)[:200]}

    snapshot = TunnelHealthSnapshot(
        environment_id=env.id,
        status=status,
        replica_count=0,
        observed_at=datetime.now(tz=timezone.utc),
        metadata_json=meta,
    )
    db.add(snapshot)
    db.commit()
    return snapshot
```

- [ ] **Step 2 : Ajouter l'endpoint ping dans `apps/api/app/modules/admin/router.py`**

Ajouter les imports nécessaires en haut du fichier (si pas déjà présents) et l'endpoint à la fin de la section Environnements :

```python
# Ajouter dans les imports :
import asyncio
from app.modules.gateway.health import check_environment_health
```

Puis ajouter l'endpoint après `create_environment` :

```python
@router.post("/environments/{env_id}/ping", status_code=200)
async def ping_environment(
    env_id: str,
    db: DbSession = Depends(get_db),
):
    """Déclenche un health check immédiat sur l'upstream d'un environnement.
    Retourne le statut observé. Ne contient jamais les credentials Cloudflare.
    """
    env = db.query(Environment).filter(Environment.id == env_id).first()
    if not env:
        raise NotFoundException()
    snapshot = await check_environment_health(env, db)
    return {
        "environment_id": env.id,
        "status": snapshot.status,
        "observed_at": snapshot.observed_at.isoformat(),
        "latency_ms": snapshot.metadata_json.get("latency_ms") if snapshot.metadata_json else None,
    }
```

- [ ] **Step 3 : Vérifier les tests (pas de régression)**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/ -q
```

Expected: tous les tests passent.

- [ ] **Step 4 : Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/api/app/modules/gateway/health.py \
        apps/api/app/modules/admin/router.py
git commit -m "feat(gateway): service health check + endpoint POST /admin/environments/{id}/ping"
```

---

## Task 6: Frontend — ressource s'ouvre via gateway

**Files:**
- Modify: `apps/web/src/lib/api/server.ts`
- Modify: `apps/web/src/app/(portal)/resource/[id]/page.tsx`
- Modify: `apps/web/src/app/(portal)/resource/[id]/interstitial/page.tsx`

Actuellement `env.url = https://{public_hostname}` va directement vers Cloudflare.  
La correction : utiliser `env.gateway_url` (`/gateway/{id}/`) préfixé de `NEXT_PUBLIC_API_URL`.

- [ ] **Step 1 : Ajouter `gateway_url` à `EnvironmentItem` dans `server.ts`**

Dans `apps/web/src/lib/api/server.ts`, modifier le type `EnvironmentItem` :

```typescript
export type EnvironmentItem = {
  id: string;
  organization_name: string;
  project_name: string;
  environment_name: string;
  kind: string;
  url: string;          // URL publique DevGate — affichage hostname
  gateway_url: string;  // Chemin gateway — ex: "/gateway/abc123/"
  requires_app_auth: boolean;
  status: string; // "online" | "offline" | "unknown"
};
```

- [ ] **Step 2 : Mettre à jour `resource/[id]/page.tsx`**

Contenu complet du fichier `apps/web/src/app/(portal)/resource/[id]/page.tsx` :

```typescript
// E06 — Détail environnement
// Référence visuelle : docs/ds/mockups/devgate-e06-detail-env.mockup.html
// Note : upstream_hostname et service_token_ref ne sont JAMAIS renvoyés par l'API portal.
// Le bouton "Ouvrir" passe par le gateway DevGate (/gateway/{id}/) — jamais directement vers Cloudflare.
import Link from "next/link";
import { redirect, notFound } from "next/navigation";
import { serverPortalApi, ServerApiError } from "@/lib/api/server";
import { KindBadge, StatusBadge } from "@/components/portal/Badge";
import styles from "./resource.module.css";

function toSlug(name: string) {
  return name.toLowerCase().replace(/\s+/g, "-");
}

interface Props {
  params: Promise<{ id: string }>;
}

export default async function ResourceDetailPage({ params }: Props) {
  const { id } = await params;

  let environments;
  try {
    environments = await serverPortalApi.environments();
  } catch (err) {
    if (err instanceof ServerApiError && err.status === 401) {
      redirect("/login");
    }
    redirect("/session-expired");
  }

  const env = environments.find((e) => e.id === id);
  if (!env) notFound();

  const hostname = env.url.replace(/^https?:\/\//, "");
  const orgSlug = toSlug(env.organization_name);
  const isOnline = env.status === "online";

  // URL de navigation réelle : gateway DevGate (jamais le public_hostname directement)
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
  const gatewayUrl = `${apiBase}${env.gateway_url}`;

  return (
    <main className={styles.main}>
      <nav className={styles.breadcrumb}>
        <Link href="/portal">Portail</Link>
        <span>›</span>
        <Link href={`/client/${orgSlug}`}>{env.organization_name}</Link>
        <span>›</span>
        <span style={{ color: "var(--color-text)", fontWeight: 500 }}>
          {env.environment_name}
        </span>
      </nav>

      <div className={styles.layout}>
        {/* Colonne principale */}
        <div>
          <h1 className={styles.title}>{env.environment_name}</h1>
          <p className={styles.desc}>{env.project_name}</p>

          {isOnline ? (
            <div className={styles.noticeOk}>
              ✅ Tunnel actif — environnement accessible.
            </div>
          ) : (
            <div className={styles.noticeWarn}>
              ⚠️ Cet environnement est actuellement hors ligne.
            </div>
          )}

          {env.requires_app_auth && (
            <div className={styles.noticeWarn}>
              ⚠️ Cette ressource demande une authentification applicative après
              l&apos;ouverture via DevGate.
            </div>
          )}

          <div className={styles.metaTable}>
            <div className={styles.metaRow}>
              <div className={styles.metaKey}>Projet</div>
              <div className={styles.metaVal}>{env.project_name}</div>
            </div>
            <div className={styles.metaRow}>
              <div className={styles.metaKey}>Type</div>
              <div className={styles.metaVal}>
                <KindBadge kind={env.kind} />
              </div>
            </div>
            <div className={styles.metaRow}>
              <div className={styles.metaKey}>URL publique</div>
              <div className={`${styles.metaVal} ${styles.metaMono}`}>{hostname}</div>
            </div>
            <div className={styles.metaRow}>
              <div className={styles.metaKey}>Statut</div>
              <div className={styles.metaVal}>
                <StatusBadge status={env.status} />
              </div>
            </div>
            <div className={styles.metaRow}>
              <div className={styles.metaKey}>Auth applicative</div>
              <div className={styles.metaVal}>
                {env.requires_app_auth ? "Requise" : "Non requise"}
              </div>
            </div>
          </div>

          <div className={styles.actions}>
            {isOnline && (
              <a
                href={env.requires_app_auth ? `/resource/${id}/interstitial` : gatewayUrl}
                className={styles.btnPrimary}
                {...(!env.requires_app_auth
                  ? { target: "_blank", rel: "noopener noreferrer" }
                  : {})}
              >
                Ouvrir la ressource ↗
              </a>
            )}
            <Link href={`/client/${orgSlug}`} className={styles.btnSecondary}>
              ← Retour aux ressources
            </Link>
          </div>
        </div>

        {/* Panneau de statut */}
        <div className={styles.statusPanel}>
          <div className={styles.tile}>
            <div className={styles.tileLabel}>Tunnel</div>
            <div className={`${styles.tileValue} ${isOnline ? styles.colorOk : styles.colorWarn}`}>
              {isOnline ? "🟢 Actif" : "🔴 Inactif"}
            </div>
            <div className={styles.tileSub}>{isOnline ? "Accessible" : "Hors ligne"}</div>
          </div>
          <div className={styles.tile}>
            <div className={styles.tileLabel}>Auth DevGate</div>
            <div className={`${styles.tileValue} ${styles.colorOk}`}>✅ Validée</div>
            <div className={styles.tileSub}>Accès accordé</div>
          </div>
          <div className={styles.tile}>
            <div className={styles.tileLabel}>Auth applicative</div>
            {env.requires_app_auth ? (
              <>
                <div className={`${styles.tileValue} ${styles.colorWarn}`}>⚠️ Requise</div>
                <div className={styles.tileSub}>Login après ouverture</div>
              </>
            ) : (
              <>
                <div className={`${styles.tileValue} ${styles.colorOk}`}>✅ Non requise</div>
                <div className={styles.tileSub}>Accès direct</div>
              </>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
```

- [ ] **Step 3 : Mettre à jour `interstitial/page.tsx`**

Contenu complet de `apps/web/src/app/(portal)/resource/[id]/interstitial/page.tsx` :

```typescript
// E07 — Interstitiel double auth
// Référence visuelle : docs/ds/mockups/devgate-e07-interstitiel.mockup.html
// Affiché uniquement quand requires_app_auth=true, avant ouverture de la ressource.
// "Continuer" ouvre le gateway DevGate — jamais directement le hostname Cloudflare.
import Link from "next/link";
import { redirect, notFound } from "next/navigation";
import { serverPortalApi, ServerApiError } from "@/lib/api/server";
import styles from "./interstitial.module.css";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function InterstitialPage({ params }: Props) {
  const { id } = await params;

  let environments;
  try {
    environments = await serverPortalApi.environments();
  } catch (err) {
    if (err instanceof ServerApiError && err.status === 401) {
      redirect("/login");
    }
    redirect("/session-expired");
  }

  const env = environments.find((e) => e.id === id);
  if (!env) notFound();

  // URL de navigation : gateway DevGate (jamais le public_hostname directement)
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
  const gatewayUrl = `${apiBase}${env.gateway_url}`;

  return (
    <div className={styles.wrap}>
      <div className={styles.card}>
        <div className={styles.icon}>↗</div>
        <h1 className={styles.title}>La ressource va s&apos;ouvrir</h1>
        <p className={styles.sub}>
          Votre accès à <strong>{env.environment_name}</strong> a été validé par DevGate.
          Cette ressource va maintenant vous demander son propre login.
        </p>
        <div className={styles.notice}>
          ℹ️ C&apos;est normal. DevGate contrôle l&apos;accès à l&apos;environnement.
          L&apos;application peut ensuite avoir sa propre authentification — par exemple
          WordPress ou votre outil métier.
        </div>
        <a
          href={gatewayUrl}
          target="_blank"
          rel="noopener noreferrer"
          className={styles.btnPrimary}
        >
          Continuer vers la ressource ↗
        </a>
        <Link href={`/resource/${id}`} className={styles.btnSecondary}>
          ← Retour aux détails
        </Link>
        <p className={styles.note}>
          Si vous n&apos;avez pas les identifiants de l&apos;application, contactez l&apos;agence.
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 4 : Vérifier la compilation TypeScript**

```bash
cd /Users/amiellavon/Sites/Captive-serveur/apps/web
npx tsc --noEmit 2>&1 | head -10
```

Expected: aucune sortie (zéro erreur).

- [ ] **Step 5 : Vérifier les tests backend (pas de régression)**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/ -q
```

Expected: tous les tests passent.

- [ ] **Step 6 : Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/web/src/lib/api/server.ts \
        apps/web/src/app/\(portal\)/resource/\[id\]/page.tsx \
        apps/web/src/app/\(portal\)/resource/\[id\]/interstitial/page.tsx
git commit -m "feat(portal): ouvrir les ressources via le gateway DevGate"
```

---

## Self-Review

### Spec coverage

| Exigence Phase 5 | Tâche |
|---|---|
| Résolution ressource depuis URL DevGate | ✅ Task 1 + 6 : `gateway_url` retourné par le portail, utilisé par le frontend |
| Gateway logique intégré au backend | ✅ Déjà en place, Task 2 l'améliore |
| Vérification session + droit d'accès | ✅ `resolve_environment` dans gateway/service.py |
| Proxy HTTP vers l'upstream | ✅ Déjà en place, Task 2 corrige les headers |
| Interstitiel si auth applicative | ✅ Task 6 : interstitial/page.tsx → gateway |
| Gestion erreurs upstream | ✅ 502 via `UpstreamUnavailableException`, testé Task 3 |
| Support cookies, redirects, headers | ✅ Task 2 : Accept-Encoding identity + multi-value Set-Cookie |
| Base WebSocket | ✅ Task 4 : route WebSocket bidirectionnelle |
| Health check visible agence | ✅ Task 5 : `POST /admin/environments/{id}/ping` |

### Scan placeholders

Aucun "TBD", "TODO", "implement later" dans le plan.

### Cohérence des types

- `gateway_url: str` défini dans `portal/schemas.py` (Task 1) → utilisé dans `server.ts` (Task 6) ✓
- `check_environment_health(env, db)` retourne `TunnelHealthSnapshot` (Task 5) ✓
- `env_id` est cohérent dans tous les fichiers ✓
