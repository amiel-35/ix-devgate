# Resource Health UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Afficher le statut de santé upstream (online/offline/unknown) de chaque environnement dans le back-office admin, avec un bouton "Tester" pour déclencher un ping immédiat.

**Architecture:** Le backend `TunnelHealthSnapshot` et l'endpoint `POST /admin/environments/{id}/ping` existent déjà. Ce plan se limite à (1) enrichir le `GET /admin/environments` avec le dernier snapshot de santé via une sous-requête SQLAlchemy, et (2) afficher le statut dans `EnvironmentsClient.tsx` avec un bouton qui appelle le ping existant. Aucun nouveau modèle ni nouvelle table.

**Tech Stack:** Python FastAPI / SQLAlchemy (backend), Next.js React (frontend), CSS Modules.

---

## Fichiers créés ou modifiés

| Fichier | Action | Responsabilité |
|---|---|---|
| `apps/api/app/modules/admin/router.py` | Modify | Enrichir `list_environments()` avec `health_status` et `health_latency_ms` |
| `apps/api/tests/integration/test_admin_router.py` | Modify | Tests health_status dans la liste |
| `apps/web/src/lib/api/server-admin.ts` | Modify | Ajouter `health_status` et `health_latency_ms` au type `AdminEnvItem` |
| `apps/web/src/lib/api/client.ts` | Modify | Ajouter `adminApi.environments.ping()` |
| `apps/web/src/app/(admin)/admin/environments/EnvironmentsClient.tsx` | Modify | Colonne Santé + bouton Tester |

---

## Task 1: Backend — `health_status` dans la liste des environnements

**Context:** `GET /admin/environments` dans `apps/api/app/modules/admin/router.py` retourne la liste des environnements mais ne contient pas le statut de santé. Le modèle `TunnelHealthSnapshot` existe dans `app.shared.models` avec les champs `environment_id`, `status` ("online" | "offline" | "unknown"), `observed_at`, `metadata_json` (qui contient `latency_ms` si disponible). L'endpoint `POST /admin/environments/{id}/ping` existe déjà et écrit un snapshot.

**Files:**
- Modify: `apps/api/app/modules/admin/router.py`
- Modify: `apps/api/tests/integration/test_admin_router.py`

- [ ] **Step 1: Écrire les tests (failing)**

Ajouter à la fin de `apps/api/tests/integration/test_admin_router.py` :

```python
from datetime import datetime, timezone
from app.shared.models import TunnelHealthSnapshot


def _make_health_snapshot(db_session, env_id="env-1", status="online", latency_ms=95):
    snap = TunnelHealthSnapshot(
        id=f"snap-{env_id}",
        environment_id=env_id,
        status=status,
        observed_at=datetime.now(tz=timezone.utc),
        metadata_json={"latency_ms": latency_ms, "status_code": 200},
    )
    db_session.add(snap)
    db_session.commit()
    return snap


def test_list_envs_health_status_null_when_no_snapshot(client, db_session):
    """health_status est None si aucun snapshot n'existe."""
    _make_admin(db_session)
    _auth(client)
    _make_org(db_session)
    _make_project(db_session)
    _make_env(db_session)

    r = client.get("/admin/environments")
    assert r.status_code == 200
    envs = r.json()
    assert len(envs) == 1
    assert envs[0]["health_status"] is None
    assert envs[0]["health_latency_ms"] is None


def test_list_envs_health_status_reflects_latest_snapshot(client, db_session):
    """health_status reflète le dernier snapshot disponible."""
    _make_admin(db_session)
    _auth(client)
    _make_org(db_session)
    _make_project(db_session)
    _make_env(db_session)
    _make_health_snapshot(db_session, env_id="env-1", status="online", latency_ms=95)

    r = client.get("/admin/environments")
    assert r.status_code == 200
    envs = r.json()
    assert envs[0]["health_status"] == "online"
    assert envs[0]["health_latency_ms"] == 95
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
cd apps/api && python -m pytest tests/integration/test_admin_router.py::test_list_envs_health_status_null_when_no_snapshot tests/integration/test_admin_router.py::test_list_envs_health_status_reflects_latest_snapshot -v
```

Expected: `KeyError: 'health_status'` ou FAIL.

- [ ] **Step 3: Modifier `list_environments()` dans `router.py`**

Dans `apps/api/app/modules/admin/router.py`, ajouter `TunnelHealthSnapshot` aux imports du modèle (ligne ~34) :

```python
from app.shared.models import (
    AccessGrant,
    AuditEvent,
    DiscoveredTunnel,
    Environment,
    Organization,
    Project,
    ProvisioningJob,
    TunnelHealthSnapshot,
    User,
)
```

Remplacer la fonction `list_environments()` (lignes ~143–165) par :

```python
@router.get("/environments")
def list_environments(db: DbSession = Depends(get_db)):
    envs = (
        db.query(Environment)
        .options(joinedload(Environment.project).joinedload(Project.organization))
        .all()
    )

    # Dernier snapshot de santé par environnement (une seule requête groupée)
    env_ids = [e.id for e in envs]
    snap_by_env: dict = {}
    if env_ids:
        latest_subq = (
            db.query(
                TunnelHealthSnapshot.environment_id,
                func.max(TunnelHealthSnapshot.observed_at).label("max_ts"),
            )
            .filter(TunnelHealthSnapshot.environment_id.in_(env_ids))
            .group_by(TunnelHealthSnapshot.environment_id)
            .subquery()
        )
        snaps = (
            db.query(TunnelHealthSnapshot)
            .join(
                latest_subq,
                (TunnelHealthSnapshot.environment_id == latest_subq.c.environment_id)
                & (TunnelHealthSnapshot.observed_at == latest_subq.c.max_ts),
            )
            .all()
        )
        snap_by_env = {s.environment_id: s for s in snaps}

    return [
        {
            "id": e.id,
            "project_id": e.project_id,
            "name": e.name,
            "slug": e.slug,
            "kind": e.kind,
            "public_hostname": e.public_hostname,
            "requires_app_auth": e.requires_app_auth,
            "status": e.status,
            "cloudflare_tunnel_id": e.cloudflare_tunnel_id,
            "org_name": e.project.organization.name,
            "project_name": e.project.name,
            "health_status": snap_by_env[e.id].status if e.id in snap_by_env else None,
            "health_latency_ms": (
                snap_by_env[e.id].metadata_json.get("latency_ms")
                if e.id in snap_by_env and snap_by_env[e.id].metadata_json
                else None
            ),
        }
        for e in envs
    ]
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

Expected: tous PASS (aucune régression).

- [ ] **Step 6: Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/api/app/modules/admin/router.py \
        apps/api/tests/integration/test_admin_router.py
git commit -m "feat(admin): enrichir GET /admin/environments avec health_status"
```

---

## Task 2: Frontend — colonne Santé + bouton Tester

**Context:** `EnvironmentsClient.tsx` affiche un tableau des environnements (colonnes : Environnement, Client/Projet, Type, Statut, Auth app). `AdminEnvItem` dans `server-admin.ts` est le type partagé entre server et client components. `adminApi.environments` dans `client.ts` contient les méthodes côté client. Le composant est un Client Component (`"use client"`), donc les interactions utilisateur (clic Tester) passent par `adminApi` et non par `serverAdminApi`.

**Files:**
- Modify: `apps/web/src/lib/api/server-admin.ts`
- Modify: `apps/web/src/lib/api/client.ts`
- Modify: `apps/web/src/app/(admin)/admin/environments/EnvironmentsClient.tsx`

- [ ] **Step 1: Mettre à jour le type `AdminEnvItem` dans `server-admin.ts`**

Dans `apps/web/src/lib/api/server-admin.ts`, remplacer le type `AdminEnvItem` :

```typescript
export type AdminEnvItem = {
  id: string;
  project_id: string;
  name: string;
  slug: string;
  kind: string;
  public_hostname: string;
  requires_app_auth: boolean;
  status: string;
  cloudflare_tunnel_id: string | null;
  org_name: string;
  project_name: string;
  health_status: "online" | "offline" | "unknown" | null;
  health_latency_ms: number | null;
};
```

- [ ] **Step 2: Ajouter `ping` à `adminApi.environments` dans `client.ts`**

Dans `apps/web/src/lib/api/client.ts`, remplacer le bloc `environments:` :

```typescript
  environments: {
    list: () => request<AdminEnvItem[]>("/admin/environments"),
    create: (data: AdminCreateEnvPayload) =>
      request<{ id: string }>("/admin/environments", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    ping: (envId: string) =>
      request<{ environment_id: string; status: string; observed_at: string; latency_ms: number | null }>(
        `/admin/environments/${envId}/ping`,
        { method: "POST" },
      ),
  },
```

- [ ] **Step 3: Mettre à jour `EnvironmentsClient.tsx`**

Remplacer le contenu intégral de `apps/web/src/app/(admin)/admin/environments/EnvironmentsClient.tsx` :

```tsx
"use client";

import { useState } from "react";
import { adminApi, AdminCreateEnvPayload } from "@/lib/api/client";
import type { AdminEnvItem, OrgItem, ProjectItem } from "@/lib/api/server-admin";
import styles from "./environments.module.css";

interface Props {
  initialEnvs: AdminEnvItem[];
  orgs: OrgItem[];
  initialProjects: ProjectItem[];
}

const KIND_LABELS: Record<string, string> = {
  staging: "Staging",
  preview: "Preview",
  dev: "Dev",
  internal: "Internal",
};

const HEALTH_COLORS: Record<string, string> = {
  online: "#16a34a",
  offline: "#dc2626",
  unknown: "#d97706",
};

const HEALTH_LABELS: Record<string, string> = {
  online: "En ligne",
  offline: "Hors ligne",
  unknown: "Inconnu",
};

function KindBadge({ kind }: { kind: string }) {
  const key = `kind${kind.charAt(0).toUpperCase() + kind.slice(1)}` as keyof typeof styles;
  const cls = styles[key] ?? styles.kindInternal;
  return (
    <span className={`${styles.kindBadge} ${cls}`}>
      {KIND_LABELS[kind] ?? kind}
    </span>
  );
}

function HealthBadge({ status, latency }: { status: string | null; latency: number | null }) {
  if (!status) {
    return <span style={{ color: "#9ca3af", fontSize: "0.85em" }}>—</span>;
  }
  const color = HEALTH_COLORS[status] ?? "#6b7280";
  return (
    <span style={{
      background: color + "22",
      color,
      padding: "2px 7px",
      borderRadius: "4px",
      fontSize: "11px",
      fontWeight: 600,
    }}>
      {HEALTH_LABELS[status] ?? status}
      {latency !== null && ` · ${latency}ms`}
    </span>
  );
}

type PingState = { loading: boolean; status: string | null; latency: number | null };

export function EnvironmentsClient({ initialEnvs, orgs, initialProjects }: Props) {
  const [envs, setEnvs] = useState(initialEnvs);
  const [projects, setProjects] = useState(initialProjects);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pingStates, setPingStates] = useState<Record<string, PingState>>({});

  const [selectedOrgId, setSelectedOrgId] = useState("");
  const [projId, setProjId] = useState("");
  const [envName, setEnvName] = useState("");
  const [envSlug, setEnvSlug] = useState("");
  const [envKind, setEnvKind] = useState("staging");
  const [hostname, setHostname] = useState("");
  const [requiresAuth, setRequiresAuth] = useState(false);

  const filteredProjects = projects.filter((p) => p.organization_id === selectedOrgId);

  function openDrawer() {
    setError(null);
    setOpen(true);
  }

  function closeDrawer() {
    setOpen(false);
    setError(null);
    setSelectedOrgId("");
    setProjId("");
    setEnvName("");
    setEnvSlug("");
    setEnvKind("staging");
    setHostname("");
    setRequiresAuth(false);
  }

  async function handlePing(envId: string) {
    setPingStates((prev) => ({ ...prev, [envId]: { loading: true, status: null, latency: null } }));
    try {
      const result = await adminApi.environments.ping(envId);
      setPingStates((prev) => ({
        ...prev,
        [envId]: { loading: false, status: result.status, latency: result.latency_ms },
      }));
    } catch {
      setPingStates((prev) => ({
        ...prev,
        [envId]: { loading: false, status: "offline", latency: null },
      }));
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const payload: AdminCreateEnvPayload = {
        project_id: projId,
        name: envName,
        slug: envSlug,
        kind: envKind,
        public_hostname: hostname,
        requires_app_auth: requiresAuth,
      };
      await adminApi.environments.create(payload);
      const updated = await adminApi.environments.list() as AdminEnvItem[];
      setEnvs(updated);
      closeDrawer();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inattendue");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={styles.page}>
      <h1 className={styles.pageTitle}>Environnements</h1>
      <p className={styles.pageSub}>Toutes les ressources gérées par DevGate</p>

      <div className={styles.toolbar}>
        <span className={styles.sectionTitle}>
          {envs.length} environnement{envs.length !== 1 ? "s" : ""}
        </span>
        <button className={styles.btnPrimary} onClick={openDrawer}>
          + Nouvel environnement
        </button>
      </div>

      <table className={styles.table}>
        <thead>
          <tr>
            <th>Environnement</th>
            <th>Client / Projet</th>
            <th>Type</th>
            <th>Statut</th>
            <th>Auth app</th>
            <th>Santé</th>
          </tr>
        </thead>
        <tbody>
          {envs.length === 0 ? (
            <tr className={styles.emptyRow}>
              <td colSpan={6}>Aucun environnement</td>
            </tr>
          ) : (
            envs.map((e) => {
              const ps = pingStates[e.id];
              const healthStatus = ps ? ps.status : e.health_status;
              const healthLatency = ps ? ps.latency : e.health_latency_ms;
              return (
                <tr key={e.id}>
                  <td>
                    <div className={styles.envName}>{e.name}</div>
                    <div className={styles.envHost}>{e.public_hostname}</div>
                  </td>
                  <td>
                    <span className={styles.orgProject}>
                      {e.org_name} / {e.project_name}
                    </span>
                  </td>
                  <td>
                    <KindBadge kind={e.kind} />
                  </td>
                  <td>
                    <span className={e.status === "active" ? styles.statusOnline : styles.statusInactive}>
                      {e.status === "active" ? "Actif" : e.status}
                    </span>
                  </td>
                  <td>
                    {e.requires_app_auth && (
                      <span className={styles.authBadge}>Auth requise</span>
                    )}
                  </td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <HealthBadge status={healthStatus} latency={healthLatency} />
                      <button
                        onClick={() => handlePing(e.id)}
                        disabled={ps?.loading}
                        className={styles.btnSecondary}
                        style={{ height: "26px", padding: "0 10px", fontSize: "11px" }}
                      >
                        {ps?.loading ? "…" : "Tester"}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>

      {open && (
        <div className={styles.overlay} onClick={closeDrawer}>
          <div className={styles.drawer} onClick={(e) => e.stopPropagation()}>
            <div className={styles.drawerTitle}>Nouvel environnement</div>
            <form onSubmit={handleCreate}>
              <div className={styles.formGroup}>
                <label className={styles.label}>Client *</label>
                <select
                  className={styles.select}
                  value={selectedOrgId}
                  onChange={(e) => {
                    setSelectedOrgId(e.target.value);
                    setProjId("");
                  }}
                  required
                >
                  <option value="">Choisir un client…</option>
                  {orgs.map((o) => (
                    <option key={o.id} value={o.id}>{o.name}</option>
                  ))}
                </select>
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Projet *</label>
                <select
                  className={styles.select}
                  value={projId}
                  onChange={(e) => setProjId(e.target.value)}
                  required
                  disabled={!selectedOrgId}
                >
                  <option value="">Choisir un projet…</option>
                  {filteredProjects.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Nom *</label>
                <input
                  className={styles.input}
                  value={envName}
                  onChange={(e) => setEnvName(e.target.value)}
                  required
                  placeholder="Staging principal"
                />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Slug *</label>
                <input
                  className={styles.input}
                  value={envSlug}
                  onChange={(e) => setEnvSlug(e.target.value)}
                  required
                  placeholder="staging"
                  pattern="[a-z0-9\-]+"
                />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Type *</label>
                <select
                  className={styles.select}
                  value={envKind}
                  onChange={(e) => setEnvKind(e.target.value)}
                >
                  <option value="staging">Staging</option>
                  <option value="preview">Preview</option>
                  <option value="dev">Dev</option>
                  <option value="internal">Internal</option>
                </select>
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Hostname public *</label>
                <input
                  className={styles.input}
                  value={hostname}
                  onChange={(e) => setHostname(e.target.value)}
                  required
                  placeholder="app.client.example.com"
                />
              </div>
              <div className={styles.checkRow}>
                <input
                  id="requires-auth"
                  type="checkbox"
                  checked={requiresAuth}
                  onChange={(e) => setRequiresAuth(e.target.checked)}
                />
                <label htmlFor="requires-auth" className={styles.checkLabel}>
                  Auth applicative requise
                </label>
              </div>
              {error && <p className={styles.errorMsg}>{error}</p>}
              <div className={styles.drawerActions}>
                <button type="button" className={styles.btnSecondary} onClick={closeDrawer}>
                  Annuler
                </button>
                <button type="submit" className={styles.btnPrimary} disabled={loading}>
                  {loading ? "Création…" : "Créer"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/web/src/lib/api/server-admin.ts \
        apps/web/src/lib/api/client.ts \
        apps/web/src/app/(admin)/admin/environments/EnvironmentsClient.tsx
git commit -m "feat(admin): colonne santé + bouton Tester dans la liste des environnements"
```

---

## Self-Review

### Spec coverage
- ✅ "vue statut ressource" (Phase 6) — table avec health_status online/offline/unknown
- ✅ "l'agence peut diagnostiquer une ressource indisponible" (DoD v1) — badge visible sans aller en base, bouton Tester disponible
- ✅ "health status visible dans l'admin" (Build plan Phase 6 livrables)

### Placeholder scan
Aucun placeholder détecté. Tous les steps contiennent le code complet.

### Type consistency
- `health_status: "online" | "offline" | "unknown" | null` — défini dans Task 2 Step 1, utilisé dans Task 2 Step 3 (`HealthBadge`)
- `health_latency_ms: number | null` — cohérent dans server-admin.ts et usage dans EnvironmentsClient.tsx
- `adminApi.environments.ping()` — défini dans Task 2 Step 2, appelé dans Task 2 Step 3

### Points hors-scope (YAGNI)
- Historique des snapshots (graphe temporel) — hors v1
- Auto-refresh périodique — hors v1
- Health check sur l'ensemble des envs en batch — hors v1
