# Portal utilisateur — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implémenter les 6 écrans du portail utilisateur (E04–E08, E12) en branchant le UI sur les endpoints backend déjà disponibles — le résultat est un portail fonctionnel utilisable par un vrai client une fois connecté.

**Architecture:** Server Components Next.js pour le rendu initial (les données viennent du backend via cookies forwarded), Client Components uniquement pour les mutations et les filtres interactifs. Aucune logique Cloudflare ni secret ne touche le frontend. CSS Modules + variables globales DS déjà définies dans `globals.css`.

**Tech Stack:** Next.js 15 · React 19 · TypeScript 5 · CSS Modules · Vitest + Testing Library · FastAPI (backend déjà implémenté) · pytest (tests backend).

**Source de vérité visuelle :** `docs/ds/mockups/devgate-e04-portal.mockup.html`, `devgate-e05-client.mockup.html`, `devgate-e06-detail-env.mockup.html`, `devgate-e07-interstitiel.mockup.html`, `devgate-e08-empty.mockup.html`, `devgate-e12-profile.mockup.html`.

---

## Contexte pré-requis

Le plan 1 est mergé sur `main`. Les endpoints portal backend sont déjà opérationnels :

| Endpoint | Résultat |
|----------|----------|
| `GET /me` | `{ id, email, display_name }` |
| `GET /me/environments` | `[{ id, organization_name, project_name, environment_name, kind, url, requires_app_auth, status }]` |
| `GET /me/sessions` | `[{ id, expires_at, last_seen_at, ip, user_agent, is_current }]` |
| `DELETE /me/sessions/{id}` | 204 No Content |

Les pages portal sont scaffoldées mais vides (`apps/web/src/app/(portal)/`). Le layout appelle déjà `requireSession()`.

---

## File Structure

### Backend (`apps/api/`)

| Fichier | Action |
|---------|--------|
| `tests/integration/test_portal_router.py` | **Create** — tests TDD des 4 endpoints portal |

### Frontend (`apps/web/`)

| Fichier | Action |
|---------|--------|
| `src/lib/api/server.ts` | **Create** — `serverRequest()` qui forward le cookie session côté Server Components |
| `src/components/portal/PortalHeader.tsx` | **Create** — header fixe (brand + user pill + Mon profil + Déconnexion) |
| `src/components/portal/PortalHeader.module.css` | **Create** |
| `src/components/portal/LogoutButton.tsx` | **Create** — Client Component pour déclencher `POST /auth/logout` |
| `src/components/portal/Badge.tsx` | **Create** — badges kind (staging/preview/dev) + status (online/offline/unknown) + auth |
| `src/components/portal/Badge.module.css` | **Create** |
| `src/components/portal/EnvCard.tsx` | **Create** — card environnement utilisée en E04 et E05 |
| `src/components/portal/EnvCard.module.css` | **Create** |
| `src/components/portal/__tests__/Badge.test.tsx` | **Create** |
| `src/components/portal/__tests__/EnvCard.test.tsx` | **Create** |
| `src/app/(portal)/layout.tsx` | **Modify** — wire `PortalHeader` avec données user chargées server-side |
| `src/app/(portal)/portal/page.tsx` | **Modify** — E04 complet (server shell + PortalDashboard) |
| `src/app/(portal)/portal/PortalDashboard.tsx` | **Create** — Client Component : banner + filter bar + grid |
| `src/app/(portal)/portal/portal.module.css` | **Create** |
| `src/app/(portal)/portal/__tests__/PortalDashboard.test.tsx` | **Create** |
| `src/app/(portal)/client/[slug]/page.tsx` | **Modify** — E05 complet |
| `src/app/(portal)/client/[slug]/client.module.css` | **Create** |
| `src/app/(portal)/resource/[id]/page.tsx` | **Modify** — E06 complet |
| `src/app/(portal)/resource/[id]/resource.module.css` | **Create** |
| `src/app/(portal)/resource/[id]/interstitial/page.tsx` | **Modify** — E07 complet |
| `src/app/(portal)/resource/[id]/interstitial/interstitial.module.css` | **Create** |
| `src/app/(portal)/profile/ProfileClient.tsx` | **Create** — Client Component : revoke sessions + update name |
| `src/app/(portal)/profile/ProfileClient.test.tsx` | **Create** |
| `src/app/(portal)/profile/page.tsx` | **Modify** — E12 server shell |
| `src/app/(portal)/profile/profile.module.css` | **Create** |

---

## Task 1 : Backend — tests intégration portal router

**Files:**
- Create: `apps/api/tests/integration/test_portal_router.py`

Les endpoints portal n'ont pas encore de tests d'intégration. Cette tâche les écrit en TDD.

- [ ] **Step 1 : Créer le fichier de test avec les helpers**

```python
# apps/api/tests/integration/test_portal_router.py
from datetime import datetime, timedelta, timezone

from app.shared.models import (
    AccessGrant, Environment, Organization,
    Project, Session as SessionModel, User,
)


def _make_user(db_session, email="user@test.com", kind="client"):
    u = User(id="u-test", email=email, display_name="Alice Test",
             kind=kind, status="active")
    db_session.add(u)
    db_session.commit()
    return u


def _make_session(db_session, user_id="u-test", session_id="s-test", days=7):
    s = SessionModel(
        id=session_id,
        user_id=user_id,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=days),
        ip="127.0.0.1",
        user_agent="TestAgent/1.0",
    )
    db_session.add(s)
    db_session.commit()
    return s


def _make_org_with_env(db_session, user_id="u-test", kind="staging", requires_app_auth=False):
    org = Organization(id="org-1", name="Client X", slug="client-x")
    proj = Project(id="proj-1", organization_id="org-1", name="Refonte site", slug="refonte")
    env = Environment(
        id="env-1",
        project_id="proj-1",
        name="Staging principal",
        slug="staging",
        kind=kind,
        public_hostname="client-x-staging.devgate.example.com",
        requires_app_auth=requires_app_auth,
        status="active",
    )
    grant = AccessGrant(
        id="grant-1",
        user_id=user_id,
        organization_id="org-1",
        role="client_member",
    )
    db_session.add_all([org, proj, env, grant])
    db_session.commit()
    return org, proj, env
```

- [ ] **Step 2 : Écrire les tests pour GET /me**

```python
def test_me_returns_user_info(client, db_session):
    _make_user(db_session)
    _make_session(db_session)
    client.cookies.set("devgate_session", "s-test")

    res = client.get("/me")

    assert res.status_code == 200
    body = res.json()
    assert body["id"] == "u-test"
    assert body["email"] == "user@test.com"
    assert body["display_name"] == "Alice Test"


def test_me_unauthenticated_returns_401(client):
    res = client.get("/me")
    assert res.status_code == 401
```

- [ ] **Step 3 : Écrire les tests pour GET /me/environments**

```python
def test_environments_returns_granted_envs(client, db_session):
    _make_user(db_session)
    _make_session(db_session)
    _make_org_with_env(db_session, requires_app_auth=True)
    client.cookies.set("devgate_session", "s-test")

    res = client.get("/me/environments")

    assert res.status_code == 200
    envs = res.json()
    assert len(envs) == 1
    e = envs[0]
    assert e["id"] == "env-1"
    assert e["organization_name"] == "Client X"
    assert e["project_name"] == "Refonte site"
    assert e["environment_name"] == "Staging principal"
    assert e["kind"] == "staging"
    assert e["url"] == "https://client-x-staging.devgate.example.com"
    assert e["requires_app_auth"] is True
    assert e["status"] == "unknown"  # pas de TunnelHealthSnapshot


def test_environments_empty_without_grants(client, db_session):
    _make_user(db_session)
    _make_session(db_session)
    client.cookies.set("devgate_session", "s-test")

    res = client.get("/me/environments")

    assert res.status_code == 200
    assert res.json() == []


def test_environments_unauthenticated_returns_401(client):
    res = client.get("/me/environments")
    assert res.status_code == 401
```

- [ ] **Step 4 : Écrire les tests pour GET /me/sessions**

```python
def test_sessions_returns_all_user_sessions(client, db_session):
    _make_user(db_session)
    _make_session(db_session, session_id="s-test")
    # deuxième session
    s2 = SessionModel(
        id="s-other",
        user_id="u-test",
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=5),
        ip="10.0.0.1",
        user_agent="OtherAgent",
    )
    db_session.add(s2)
    db_session.commit()
    client.cookies.set("devgate_session", "s-test")

    res = client.get("/me/sessions")

    assert res.status_code == 200
    sessions = res.json()
    assert len(sessions) == 2
    current = next(s for s in sessions if s["id"] == "s-test")
    assert current["is_current"] is True
    other = next(s for s in sessions if s["id"] == "s-other")
    assert other["is_current"] is False


def test_sessions_unauthenticated_returns_401(client):
    res = client.get("/me/sessions")
    assert res.status_code == 401
```

- [ ] **Step 5 : Écrire les tests pour DELETE /me/sessions/{id}**

```python
def test_revoke_other_session_returns_204(client, db_session):
    _make_user(db_session)
    _make_session(db_session, session_id="s-test")
    s2 = SessionModel(
        id="s-revoke",
        user_id="u-test",
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=5),
    )
    db_session.add(s2)
    db_session.commit()
    client.cookies.set("devgate_session", "s-test")

    res = client.delete("/me/sessions/s-revoke")

    assert res.status_code == 204
    assert db_session.get(SessionModel, "s-revoke") is None


def test_cannot_revoke_current_session(client, db_session):
    _make_user(db_session)
    _make_session(db_session, session_id="s-test")
    client.cookies.set("devgate_session", "s-test")

    res = client.delete("/me/sessions/s-test")

    # Le backend silently ignore — la session doit encore exister
    assert res.status_code == 204
    assert db_session.get(SessionModel, "s-test") is not None


def test_revoke_session_of_other_user_does_nothing(client, db_session):
    _make_user(db_session, email="a@test.com")
    _make_session(db_session, user_id="u-test", session_id="s-test")
    other = User(id="u-other", email="b@test.com", display_name="B",
                 kind="client", status="active")
    s_other = SessionModel(
        id="s-foreign",
        user_id="u-other",
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=5),
    )
    db_session.add_all([other, s_other])
    db_session.commit()
    client.cookies.set("devgate_session", "s-test")

    res = client.delete("/me/sessions/s-foreign")

    assert res.status_code == 204
    assert db_session.get(SessionModel, "s-foreign") is not None
```

- [ ] **Step 6 : Lancer les tests — vérifier qu'ils passent**

```bash
cd apps/api && python -m pytest tests/integration/test_portal_router.py -v
```

Expected: 10 tests PASSED.

- [ ] **Step 7 : Commit**

```bash
git add apps/api/tests/integration/test_portal_router.py
git commit -m "test(api): add portal router integration tests (10 tests)"
```

---

## Task 2 : Frontend — server-side API helper

**Files:**
- Create: `apps/web/src/lib/api/server.ts`

Les Server Components Next.js ne transmettent pas les cookies automatiquement — il faut les forwarder manuellement depuis `next/headers`.

- [ ] **Step 1 : Créer `server.ts`**

```typescript
// apps/web/src/lib/api/server.ts
// Helper pour appeler l'API depuis les Server Components.
// Les Server Components ne transmettent pas automatiquement les cookies :
// on les lit de next/headers et on les forward dans l'en-tête Cookie.

import { cookies } from "next/headers";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

export class ServerApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ServerApiError";
  }
}

async function serverRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const cookieStore = await cookies();
  const cookieHeader = cookieStore
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Cookie: cookieHeader,
      ...options.headers,
    },
    cache: "no-store", // toujours fraîche — pas de cache statique sur les données utilisateur
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ServerApiError(res.status, body.detail ?? res.statusText);
  }

  return res.json() as Promise<T>;
}

// ── Types partagés ────────────────────────────────────────────────

export type MeResponse = {
  id: string;
  email: string;
  display_name: string | null;
};

export type EnvironmentItem = {
  id: string;
  organization_name: string;
  project_name: string;
  environment_name: string;
  kind: string;
  url: string;
  requires_app_auth: boolean;
  status: string; // "online" | "offline" | "unknown"
};

export type SessionItem = {
  id: string;
  expires_at: string;
  last_seen_at: string;
  ip: string | null;
  user_agent: string | null;
  is_current: boolean;
};

// ── API Portal (server-side) ──────────────────────────────────────

export const serverPortalApi = {
  me: () => serverRequest<MeResponse>("/me"),
  environments: () => serverRequest<EnvironmentItem[]>("/me/environments"),
  sessions: () => serverRequest<SessionItem[]>("/me/sessions"),
};
```

- [ ] **Step 2 : Vérifier la compilation TypeScript**

```bash
cd apps/web && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3 : Commit**

```bash
git add apps/web/src/lib/api/server.ts
git commit -m "feat(web): add server-side API helper for Server Components"
```

---

## Task 3 : Frontend — Badge component

**Files:**
- Create: `apps/web/src/components/portal/Badge.tsx`
- Create: `apps/web/src/components/portal/Badge.module.css`
- Create: `apps/web/src/components/portal/__tests__/Badge.test.tsx`

- [ ] **Step 1 : Écrire le test en premier**

```typescript
// apps/web/src/components/portal/__tests__/Badge.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { KindBadge, StatusBadge, AuthBadge } from "../Badge";

describe("KindBadge", () => {
  it("renders 'staging' label", () => {
    render(<KindBadge kind="staging" />);
    expect(screen.getByText("staging")).toBeInTheDocument();
  });

  it("renders 'preview' label", () => {
    render(<KindBadge kind="preview" />);
    expect(screen.getByText("preview")).toBeInTheDocument();
  });

  it("renders 'dev' label", () => {
    render(<KindBadge kind="dev" />);
    expect(screen.getByText("dev")).toBeInTheDocument();
  });
});

describe("StatusBadge", () => {
  it("renders 'En ligne' for online status", () => {
    render(<StatusBadge status="online" />);
    expect(screen.getByText("En ligne")).toBeInTheDocument();
  });

  it("renders 'Hors ligne' for offline status", () => {
    render(<StatusBadge status="offline" />);
    expect(screen.getByText("Hors ligne")).toBeInTheDocument();
  });

  it("renders 'Inconnu' for unknown status", () => {
    render(<StatusBadge status="unknown" />);
    expect(screen.getByText("Inconnu")).toBeInTheDocument();
  });
});

describe("AuthBadge", () => {
  it("renders when shown", () => {
    render(<AuthBadge />);
    expect(screen.getByText("Auth requise")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2 : Lancer le test — vérifier qu'il échoue**

```bash
cd apps/web && npx vitest run src/components/portal/__tests__/Badge.test.tsx
```

Expected: FAIL — cannot find module `../Badge`.

- [ ] **Step 3 : Créer `Badge.module.css`**

```css
/* apps/web/src/components/portal/Badge.module.css */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 20px;
  white-space: nowrap;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}

/* kind badges */
.staging  { background: var(--color-info-bg,   #cffafe); color: var(--color-info,   #0891b2); }
.preview  { background: var(--color-warning-bg);          color: var(--color-warning); }
.dev      { background: var(--color-primary-s);           color: var(--color-primary); }
.internal { background: var(--color-surface-2);           color: var(--color-text-muted); }

/* status badges */
.online  { background: var(--color-success-bg); color: var(--color-success); }
.offline { background: var(--color-danger-bg);  color: var(--color-danger); }
.unknown { background: var(--color-surface-2);  color: var(--color-text-muted); }

/* auth badge */
.auth { background: var(--color-warning-bg); color: var(--color-warning); }
```

- [ ] **Step 4 : Créer `Badge.tsx`**

```typescript
// apps/web/src/components/portal/Badge.tsx
import styles from "./Badge.module.css";

interface KindBadgeProps {
  kind: string; // "staging" | "preview" | "dev" | "internal"
}

export function KindBadge({ kind }: KindBadgeProps) {
  const cls = styles[kind as keyof typeof styles] ?? styles.internal;
  return (
    <span className={`${styles.badge} ${cls}`}>
      {kind}
    </span>
  );
}

interface StatusBadgeProps {
  status: string; // "online" | "offline" | "unknown"
}

const STATUS_LABELS: Record<string, string> = {
  online: "En ligne",
  offline: "Hors ligne",
  unknown: "Inconnu",
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const cls = styles[status as keyof typeof styles] ?? styles.unknown;
  const label = STATUS_LABELS[status] ?? "Inconnu";
  return (
    <span className={`${styles.badge} ${cls}`}>
      <span className={styles.dot} />
      {label}
    </span>
  );
}

export function AuthBadge() {
  return (
    <span className={`${styles.badge} ${styles.auth}`}>
      🔒 Auth requise
    </span>
  );
}
```

- [ ] **Step 5 : Lancer les tests — vérifier qu'ils passent**

```bash
cd apps/web && npx vitest run src/components/portal/__tests__/Badge.test.tsx
```

Expected: 7 tests PASSED.

- [ ] **Step 6 : Commit**

```bash
git add apps/web/src/components/portal/Badge.tsx apps/web/src/components/portal/Badge.module.css apps/web/src/components/portal/__tests__/Badge.test.tsx
git commit -m "feat(web): add Badge component (KindBadge, StatusBadge, AuthBadge)"
```

---

## Task 4 : Frontend — EnvCard component

**Files:**
- Create: `apps/web/src/components/portal/EnvCard.tsx`
- Create: `apps/web/src/components/portal/EnvCard.module.css`
- Create: `apps/web/src/components/portal/__tests__/EnvCard.test.tsx`

- [ ] **Step 1 : Écrire le test en premier**

```typescript
// apps/web/src/components/portal/__tests__/EnvCard.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { EnvCard } from "../EnvCard";

const BASE_ENV = {
  id: "env-1",
  organization_name: "Client X",
  project_name: "Refonte site",
  environment_name: "Staging principal",
  kind: "staging",
  url: "https://client-x.devgate.example.com",
  requires_app_auth: false,
  status: "online",
};

describe("EnvCard", () => {
  it("renders org name, project name, env name", () => {
    render(<EnvCard env={BASE_ENV} />);
    expect(screen.getByText("Client X")).toBeInTheDocument();
    expect(screen.getByText("Refonte site")).toBeInTheDocument();
    expect(screen.getByText("Staging principal")).toBeInTheDocument();
  });

  it("renders kind badge", () => {
    render(<EnvCard env={BASE_ENV} />);
    expect(screen.getByText("staging")).toBeInTheDocument();
  });

  it("renders Accéder link when online", () => {
    render(<EnvCard env={BASE_ENV} />);
    expect(screen.getByText("Accéder ↗")).toBeInTheDocument();
  });

  it("renders Indisponible disabled button when offline", () => {
    render(<EnvCard env={{ ...BASE_ENV, status: "offline" }} />);
    const btn = screen.getByText("Indisponible");
    expect(btn).toBeInTheDocument();
    expect(btn.closest("span")).toHaveClass("disabled");
  });

  it("renders auth badge when requires_app_auth is true", () => {
    render(<EnvCard env={{ ...BASE_ENV, requires_app_auth: true }} />);
    expect(screen.getByText("🔒 Auth requise")).toBeInTheDocument();
  });

  it("shows public hostname in footer", () => {
    render(<EnvCard env={BASE_ENV} />);
    expect(screen.getByText("client-x.devgate.example.com")).toBeInTheDocument();
  });

  it("Accéder links to /resource/{id}", () => {
    render(<EnvCard env={BASE_ENV} />);
    const link = screen.getByText("Accéder ↗").closest("a");
    expect(link).toHaveAttribute("href", "/resource/env-1");
  });
});
```

- [ ] **Step 2 : Lancer le test — vérifier qu'il échoue**

```bash
cd apps/web && npx vitest run src/components/portal/__tests__/EnvCard.test.tsx
```

Expected: FAIL — cannot find module `../EnvCard`.

- [ ] **Step 3 : Créer `EnvCard.module.css`**

```css
/* apps/web/src/components/portal/EnvCard.module.css */
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 18px 20px;
  transition: box-shadow 0.18s, border-color 0.18s, transform 0.14s;
  text-decoration: none;
  color: inherit;
  display: block;
}

.card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--color-primary);
  transform: translateY(-1px);
}

.top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 10px;
}

.org {
  font-size: 10px;
  font-weight: 700;
  color: var(--color-text-subtle);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 2px;
}

.project {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 1px;
}

.envName {
  font-size: 13px;
  color: var(--color-text-muted);
}

.meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
}

.hostname {
  font-size: 11px;
  font-family: monospace;
  color: var(--color-text-subtle);
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.accessBtn {
  font-family: var(--font);
  font-size: 12px;
  font-weight: 600;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  padding: 6px 13px;
  cursor: pointer;
  white-space: nowrap;
  text-decoration: none;
  display: inline-block;
  transition: background 0.12s;
}

.accessBtn:hover {
  background: var(--color-primary-h);
}

.disabled {
  font-size: 12px;
  font-weight: 600;
  background: var(--color-primary);
  color: #fff;
  border-radius: var(--radius-sm);
  padding: 6px 13px;
  white-space: nowrap;
  display: inline-block;
  opacity: 0.45;
  pointer-events: none;
}
```

- [ ] **Step 4 : Créer `EnvCard.tsx`**

```typescript
// apps/web/src/components/portal/EnvCard.tsx
import Link from "next/link";
import { KindBadge, StatusBadge, AuthBadge } from "./Badge";
import type { EnvironmentItem } from "@/lib/api/server";
import styles from "./EnvCard.module.css";

interface Props {
  env: EnvironmentItem;
}

export function EnvCard({ env }: Props) {
  // Extrait juste le hostname pour l'affichage (sans https://)
  const hostname = env.url.replace(/^https?:\/\//, "");

  return (
    <Link href={`/resource/${env.id}`} className={styles.card}>
      <div className={styles.top}>
        <div>
          <div className={styles.org}>{env.organization_name}</div>
          <div className={styles.project}>{env.project_name}</div>
          <div className={styles.envName}>{env.environment_name}</div>
        </div>
        <KindBadge kind={env.kind} />
      </div>

      <div className={styles.meta}>
        <StatusBadge status={env.status} />
        {env.requires_app_auth && <AuthBadge />}
      </div>

      <div className={styles.footer}>
        <span className={styles.hostname}>{hostname}</span>
        {env.status === "offline" ? (
          <span className={styles.disabled}>Indisponible</span>
        ) : (
          <span className={styles.accessBtn}>Accéder ↗</span>
        )}
      </div>
    </Link>
  );
}
```

- [ ] **Step 5 : Lancer les tests — vérifier qu'ils passent**

```bash
cd apps/web && npx vitest run src/components/portal/__tests__/EnvCard.test.tsx
```

Expected: 7 tests PASSED.

- [ ] **Step 6 : Commit**

```bash
git add apps/web/src/components/portal/
git commit -m "feat(web): add EnvCard component"
```

---

## Task 5 : Frontend — PortalHeader + LogoutButton + Portal layout

**Files:**
- Create: `apps/web/src/components/portal/LogoutButton.tsx`
- Create: `apps/web/src/components/portal/PortalHeader.tsx`
- Create: `apps/web/src/components/portal/PortalHeader.module.css`
- Modify: `apps/web/src/app/(portal)/layout.tsx`

- [ ] **Step 1 : Créer `LogoutButton.tsx` (Client Component)**

```typescript
// apps/web/src/components/portal/LogoutButton.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api/client";
import styles from "./PortalHeader.module.css";

export function LogoutButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function handleLogout() {
    setLoading(true);
    try {
      await authApi.logout();
    } finally {
      router.push("/login");
    }
  }

  return (
    <button className={styles.ghostBtn} onClick={handleLogout} disabled={loading}>
      {loading ? "…" : "Déconnexion"}
    </button>
  );
}
```

- [ ] **Step 2 : Créer `PortalHeader.module.css`**

```css
/* apps/web/src/components/portal/PortalHeader.module.css */
.header {
  position: sticky;
  top: 0;
  z-index: 90;
  height: 56px;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 36px;
  box-shadow: var(--shadow-sm);
}

.brand {
  display: flex;
  align-items: center;
  gap: 9px;
}

.logo {
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, var(--color-primary), #7c3aed);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.brandName {
  font-size: 14px;
  font-weight: 700;
}

.sep {
  width: 1px;
  height: 15px;
  background: var(--color-border);
  margin: 0 2px;
}

.portalLabel {
  font-size: 13px;
  color: var(--color-text-muted);
}

.userRow {
  display: flex;
  align-items: center;
  gap: 8px;
}

.avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}

.userName {
  font-size: 13px;
  font-weight: 500;
}

.ghostBtn {
  font-family: var(--font);
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-muted);
  background: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 4px 10px;
  cursor: pointer;
  transition: background 0.12s;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
}

.ghostBtn:hover {
  background: var(--color-surface-2);
}

.ghostBtn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
```

- [ ] **Step 3 : Créer `PortalHeader.tsx`**

```typescript
// apps/web/src/components/portal/PortalHeader.tsx
// Server Component — reçoit les données user en props depuis le layout.
import Link from "next/link";
import type { MeResponse } from "@/lib/api/server";
import { LogoutButton } from "./LogoutButton";
import styles from "./PortalHeader.module.css";

interface Props {
  user: MeResponse;
}

function initials(user: MeResponse): string {
  const name = user.display_name ?? user.email;
  return name
    .split(/[\s@]/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join("");
}

export function PortalHeader({ user }: Props) {
  const displayName = user.display_name ?? user.email.split("@")[0];

  return (
    <header className={styles.header}>
      <div className={styles.brand}>
        <div className={styles.logo}>AG</div>
        <span className={styles.brandName}>Agence</span>
        <div className={styles.sep} />
        <span className={styles.portalLabel}>DevGate</span>
      </div>
      <div className={styles.userRow}>
        <div className={styles.avatar}>{initials(user)}</div>
        <span className={styles.userName}>{displayName}</span>
        <Link href="/profile" className={styles.ghostBtn}>
          Mon profil
        </Link>
        <LogoutButton />
      </div>
    </header>
  );
}
```

- [ ] **Step 4 : Modifier `(portal)/layout.tsx`**

```typescript
// apps/web/src/app/(portal)/layout.tsx
import { redirect } from "next/navigation";
import { requireSession } from "@/lib/auth/session";
import { serverPortalApi, ServerApiError } from "@/lib/api/server";
import { PortalHeader } from "@/components/portal/PortalHeader";
import type { ReactNode } from "react";

export default async function PortalLayout({ children }: { children: ReactNode }) {
  await requireSession();

  let user;
  try {
    user = await serverPortalApi.me();
  } catch (err) {
    if (err instanceof ServerApiError && err.status === 401) {
      redirect("/login");
    }
    redirect("/session-expired");
  }

  return (
    <div>
      <PortalHeader user={user} />
      <main>{children}</main>
    </div>
  );
}
```

- [ ] **Step 5 : Vérifier la compilation**

```bash
cd apps/web && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 6 : Commit**

```bash
git add apps/web/src/components/portal/LogoutButton.tsx \
        apps/web/src/components/portal/PortalHeader.tsx \
        apps/web/src/components/portal/PortalHeader.module.css \
        apps/web/src/app/(portal)/layout.tsx
git commit -m "feat(web): add PortalHeader with user data + wire portal layout"
```

---

## Task 6 : Frontend — E04 Portal dashboard

**Files:**
- Create: `apps/web/src/app/(portal)/portal/PortalDashboard.tsx`
- Create: `apps/web/src/app/(portal)/portal/portal.module.css`
- Create: `apps/web/src/app/(portal)/portal/__tests__/PortalDashboard.test.tsx`
- Modify: `apps/web/src/app/(portal)/portal/page.tsx`

La page E04 montre un banner de bienvenue, un filtre, et une grille d'environnements. Le filtre est interactif → Client Component. Les données sont chargées côté serveur.

- [ ] **Step 1 : Écrire le test PortalDashboard**

```typescript
// apps/web/src/app/(portal)/portal/__tests__/PortalDashboard.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PortalDashboard } from "../PortalDashboard";
import type { EnvironmentItem, MeResponse } from "@/lib/api/server";

const USER: MeResponse = { id: "u1", email: "alice@test.com", display_name: "Alice" };

const ENVS: EnvironmentItem[] = [
  {
    id: "e1",
    organization_name: "Client X",
    project_name: "Site corporate",
    environment_name: "Staging principal",
    kind: "staging",
    url: "https://cx-staging.example.com",
    requires_app_auth: false,
    status: "online",
  },
  {
    id: "e2",
    organization_name: "Client X",
    project_name: "App mobile",
    environment_name: "Preview feature",
    kind: "preview",
    url: "https://cx-preview.example.com",
    requires_app_auth: true,
    status: "online",
  },
];

describe("PortalDashboard", () => {
  it("renders welcome banner with user name", () => {
    render(<PortalDashboard user={USER} environments={ENVS} />);
    expect(screen.getByText(/Bonjour Alice/)).toBeInTheDocument();
  });

  it("renders metric: number of environments", () => {
    render(<PortalDashboard user={USER} environments={ENVS} />);
    expect(screen.getByText("2")).toBeInTheDocument(); // count
  });

  it("renders all env cards initially", () => {
    render(<PortalDashboard user={USER} environments={ENVS} />);
    expect(screen.getByText("Staging principal")).toBeInTheDocument();
    expect(screen.getByText("Preview feature")).toBeInTheDocument();
  });

  it("filters by kind when clicking staging chip", async () => {
    render(<PortalDashboard user={USER} environments={ENVS} />);
    await userEvent.click(screen.getByRole("button", { name: "Staging" }));
    expect(screen.getByText("Staging principal")).toBeInTheDocument();
    expect(screen.queryByText("Preview feature")).not.toBeInTheDocument();
  });

  it("filters by search input", async () => {
    render(<PortalDashboard user={USER} environments={ENVS} />);
    await userEvent.type(screen.getByPlaceholderText("Rechercher…"), "App");
    expect(screen.queryByText("Staging principal")).not.toBeInTheDocument();
    expect(screen.getByText("Preview feature")).toBeInTheDocument();
  });

  it("shows empty state when no environments", () => {
    render(<PortalDashboard user={USER} environments={[]} />);
    expect(screen.getByText("Aucune ressource visible")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2 : Lancer le test — vérifier qu'il échoue**

```bash
cd apps/web && npx vitest run src/app/\(portal\)/portal/__tests__/PortalDashboard.test.tsx
```

Expected: FAIL — cannot find module `../PortalDashboard`.

- [ ] **Step 3 : Créer `portal.module.css`**

```css
/* apps/web/src/app/(portal)/portal/portal.module.css */
.main {
  padding: 36px;
  max-width: 1060px;
  margin: 0 auto;
}

/* Welcome banner */
.banner {
  background: linear-gradient(135deg, #1e3a5f, #1e2d4f);
  border-radius: var(--radius-lg);
  padding: 26px 30px;
  color: #fff;
  margin-bottom: 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.bannerText h2 {
  font-size: 19px;
  font-weight: 700;
  margin-bottom: 5px;
}

.bannerText p {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.72);
  line-height: 1.5;
}

.metrics {
  display: flex;
  gap: 20px;
  flex-shrink: 0;
}

.metric {
  text-align: center;
}

.metricValue {
  font-size: 26px;
  font-weight: 700;
}

.metricLabel {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.6);
  margin-top: 2px;
}

/* Filters */
.filters {
  display: flex;
  gap: 8px;
  margin-bottom: 18px;
  align-items: center;
  flex-wrap: wrap;
}

.searchInput {
  flex: 1;
  max-width: 240px;
  padding: 8px 10px 8px 32px;
  font-family: var(--font);
  font-size: 13px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text);
  outline: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='13' height='13' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cpath d='m21 21-4.35-4.35'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: 9px center;
}

.chip {
  font-family: var(--font);
  font-size: 12px;
  font-weight: 500;
  padding: 4px 11px;
  border-radius: 20px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-muted);
  cursor: pointer;
  transition: all 0.12s;
}

.chipActive {
  background: var(--color-primary-s);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

/* Grid */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
}

.pageTitle {
  font-size: 19px;
  font-weight: 700;
  letter-spacing: -0.3px;
  margin-bottom: 3px;
}

.pageSub {
  font-size: 13px;
  color: var(--color-text-muted);
  margin-bottom: 22px;
}

/* Empty state */
.emptyWrap {
  display: flex;
  justify-content: center;
  padding: 60px 0;
}

.emptyCard {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  width: 100%;
  max-width: 480px;
  padding: 48px 40px 40px;
  text-align: center;
}

.emptyIcon {
  font-size: 40px;
  margin-bottom: 20px;
}

.emptyTitle {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.3px;
  margin-bottom: 10px;
}

.emptyDesc {
  font-size: 14px;
  color: var(--color-text-muted);
  line-height: 1.6;
  margin-bottom: 26px;
}

@media (max-width: 600px) {
  .main { padding: 20px 14px; }
  .metrics { display: none; }
}
```

- [ ] **Step 4 : Créer `PortalDashboard.tsx`**

```typescript
// apps/web/src/app/(portal)/portal/PortalDashboard.tsx
"use client";

import { useState, useMemo } from "react";
import { EnvCard } from "@/components/portal/EnvCard";
import type { EnvironmentItem, MeResponse } from "@/lib/api/server";
import styles from "./portal.module.css";

const KIND_FILTERS = [
  { label: "Tous", value: "" },
  { label: "Staging", value: "staging" },
  { label: "Preview", value: "preview" },
  { label: "Dev", value: "dev" },
];

interface Props {
  user: MeResponse;
  environments: EnvironmentItem[];
}

export function PortalDashboard({ user, environments }: Props) {
  const [search, setSearch] = useState("");
  const [kindFilter, setKindFilter] = useState("");

  const filtered = useMemo(() => {
    return environments.filter((e) => {
      const matchKind = kindFilter === "" || e.kind === kindFilter;
      const q = search.toLowerCase();
      const matchSearch =
        q === "" ||
        e.organization_name.toLowerCase().includes(q) ||
        e.project_name.toLowerCase().includes(q) ||
        e.environment_name.toLowerCase().includes(q);
      return matchKind && matchSearch;
    });
  }, [environments, search, kindFilter]);

  const firstName = (user.display_name ?? user.email).split(/[\s@]/)[0];

  if (environments.length === 0) {
    return (
      <div className={styles.main}>
        <div className={styles.emptyWrap}>
          <div className={styles.emptyCard}>
            <div className={styles.emptyIcon}>📭</div>
            <h1 className={styles.emptyTitle}>Aucune ressource visible</h1>
            <p className={styles.emptyDesc}>
              Votre compte est bien reconnu, mais aucune ressource active n&apos;est
              disponible pour le moment.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.main}>
      <div className={styles.banner}>
        <div className={styles.bannerText}>
          <h2>Bonjour {firstName}, vos accès sont prêts.</h2>
          <p>Retrouvez ci-dessous les ressources disponibles sur votre compte.</p>
        </div>
        <div className={styles.metrics}>
          <div className={styles.metric}>
            <div className={styles.metricValue}>{environments.length}</div>
            <div className={styles.metricLabel}>Environnements</div>
          </div>
        </div>
      </div>

      <div className={styles.pageTitle}>Mes environnements</div>
      <div className={styles.pageSub}>
        {filtered.length} ressource{filtered.length !== 1 ? "s" : ""} accessible
        {filtered.length !== 1 ? "s" : ""}
      </div>

      <div className={styles.filters}>
        <input
          className={styles.searchInput}
          type="text"
          placeholder="Rechercher…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {KIND_FILTERS.map((f) => (
          <button
            key={f.value}
            className={`${styles.chip} ${kindFilter === f.value ? styles.chipActive : ""}`}
            onClick={() => setKindFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className={styles.grid}>
        {filtered.map((env) => (
          <EnvCard key={env.id} env={env} />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 5 : Modifier `portal/page.tsx`**

```typescript
// apps/web/src/app/(portal)/portal/page.tsx
// E04 — Portail (accueil post-login)
// Référence visuelle : docs/ds/mockups/devgate-e04-portal.mockup.html
import { redirect } from "next/navigation";
import { serverPortalApi, ServerApiError } from "@/lib/api/server";
import { PortalDashboard } from "./PortalDashboard";

export default async function PortalPage() {
  let user;
  let environments;

  try {
    [user, environments] = await Promise.all([
      serverPortalApi.me(),
      serverPortalApi.environments(),
    ]);
  } catch (err) {
    if (err instanceof ServerApiError && err.status === 401) {
      redirect("/login");
    }
    redirect("/session-expired");
  }

  return <PortalDashboard user={user} environments={environments} />;
}
```

- [ ] **Step 6 : Lancer les tests**

```bash
cd apps/web && npx vitest run src/app/\(portal\)/portal/__tests__/PortalDashboard.test.tsx
```

Expected: 6 tests PASSED.

- [ ] **Step 7 : Commit**

```bash
git add apps/web/src/app/\(portal\)/portal/
git commit -m "feat(web): E04 portal dashboard — welcome banner, filter bar, env grid"
```

---

## Task 7 : Frontend — E05 Client page

**Files:**
- Modify: `apps/web/src/app/(portal)/client/[slug]/page.tsx`
- Create: `apps/web/src/app/(portal)/client/[slug]/client.module.css`

La page affiche une sidebar avec les organisations accessibles et filtre les envs de l'org sélectionnée (= slug dans l'URL).

- [ ] **Step 1 : Créer `client.module.css`**

```css
/* apps/web/src/app/(portal)/client/[slug]/client.module.css */
.layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  min-height: calc(100vh - 56px);
}

.sidebar {
  border-right: 1px solid var(--color-border);
  padding: 22px 14px;
  background: var(--color-surface);
}

.sbLabel {
  font-size: 10px;
  font-weight: 700;
  color: var(--color-text-subtle);
  text-transform: uppercase;
  letter-spacing: 0.07em;
  margin-bottom: 10px;
}

.clientItem {
  padding: 10px 12px;
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  margin-bottom: 7px;
  text-decoration: none;
  display: block;
  color: inherit;
  transition: background 0.12s;
}

.clientItem:hover {
  background: var(--color-surface-2);
}

.clientItemActive {
  background: var(--color-primary-s);
  border-color: var(--color-primary);
}

.clientName {
  font-size: 14px;
  font-weight: 700;
}

.clientItemActive .clientName {
  color: var(--color-primary);
}

.clientCount {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

.main {
  padding: 28px 32px;
}

.pageTitle {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.3px;
  margin-bottom: 3px;
}

.pageSub {
  font-size: 13px;
  color: var(--color-text-muted);
  margin-bottom: 18px;
}

.notice {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 11px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.5;
  margin-bottom: 18px;
  background: #cffafe;
  color: #0891b2;
}

.cards {
  display: flex;
  flex-direction: column;
  gap: 13px;
}

/* Réutilise .card mais en layout vertical (col unique) */
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 18px 20px;
  transition: box-shadow 0.18s, border-color 0.18s;
}

.card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--color-primary);
}

.top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 10px;
}

.org {
  font-size: 10px;
  font-weight: 700;
  color: var(--color-text-subtle);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 2px;
}

.project {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 2px;
}

.envName {
  font-size: 13px;
  color: var(--color-text-muted);
}

.meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
}

.hostname {
  font-size: 11px;
  font-family: monospace;
  color: var(--color-text-subtle);
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.actions {
  display: flex;
  gap: 8px;
}

.btnPrimary {
  font-family: var(--font);
  font-size: 12px;
  font-weight: 600;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  padding: 6px 13px;
  cursor: pointer;
  text-decoration: none;
  display: inline-block;
  transition: background 0.12s;
}

.btnPrimary:hover { background: var(--color-primary-h); }

.btnSecondary {
  font-family: var(--font);
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-muted);
  background: var(--color-surface-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 5px 11px;
  cursor: pointer;
  text-decoration: none;
  display: inline-block;
}

.btnDisabled {
  font-size: 12px;
  font-weight: 600;
  background: var(--color-primary);
  color: #fff;
  border-radius: var(--radius-sm);
  padding: 6px 13px;
  opacity: 0.45;
  pointer-events: none;
  display: inline-block;
}

@media (max-width: 700px) {
  .layout { grid-template-columns: 1fr; }
  .sidebar { border-right: none; border-bottom: 1px solid var(--color-border); }
  .main { padding: 20px 14px; }
}
```

- [ ] **Step 2 : Modifier `client/[slug]/page.tsx`**

```typescript
// apps/web/src/app/(portal)/client/[slug]/page.tsx
// E05 — Page client
// Référence visuelle : docs/ds/mockups/devgate-e05-client.mockup.html
import Link from "next/link";
import { redirect, notFound } from "next/navigation";
import { serverPortalApi, ServerApiError } from "@/lib/api/server";
import { KindBadge, StatusBadge, AuthBadge } from "@/components/portal/Badge";
import styles from "./client.module.css";

// Normalise un nom d'organisation en slug URL (même logique côté portail E04)
function toSlug(name: string) {
  return name.toLowerCase().replace(/\s+/g, "-");
}

interface Props {
  params: Promise<{ slug: string }>;
}

export default async function ClientPage({ params }: Props) {
  const { slug } = await params;

  let environments;
  try {
    environments = await serverPortalApi.environments();
  } catch (err) {
    if (err instanceof ServerApiError && err.status === 401) {
      redirect("/login");
    }
    redirect("/session-expired");
  }

  // Grouper les environnements par organisation
  const orgMap = new Map<string, { name: string; slug: string; envs: typeof environments }>();
  for (const env of environments) {
    const orgSlug = toSlug(env.organization_name);
    if (!orgMap.has(orgSlug)) {
      orgMap.set(orgSlug, { name: env.organization_name, slug: orgSlug, envs: [] });
    }
    orgMap.get(orgSlug)!.envs.push(env);
  }

  const currentOrg = orgMap.get(slug);
  if (!currentOrg && orgMap.size > 0) {
    // slug inconnu → rediriger vers le premier client
    const firstSlug = orgMap.keys().next().value!;
    redirect(`/client/${firstSlug}`);
  }
  if (!currentOrg) notFound();

  const clientEnvs = currentOrg.envs;

  return (
    <div className={styles.layout}>
      <aside className={styles.sidebar}>
        <div className={styles.sbLabel}>Mes clients</div>
        {Array.from(orgMap.values()).map((org) => (
          <Link
            key={org.slug}
            href={`/client/${org.slug}`}
            className={`${styles.clientItem} ${org.slug === slug ? styles.clientItemActive : ""}`}
          >
            <div className={styles.clientName}>{org.name}</div>
            <div className={styles.clientCount}>
              {org.envs.length} ressource{org.envs.length !== 1 ? "s" : ""}
            </div>
          </Link>
        ))}
      </aside>

      <main className={styles.main}>
        <div className={styles.pageTitle}>{currentOrg.name}</div>
        <div className={styles.pageSub}>
          Ressources de validation disponibles pour votre compte
        </div>

        {clientEnvs.some((e) => e.requires_app_auth) && (
          <div className={styles.notice}>
            ℹ️ Certaines ressources peuvent demander une authentification
            supplémentaire propre à l&apos;application une fois ouvertes.
          </div>
        )}

        <div className={styles.cards}>
          {clientEnvs.map((env) => {
            const hostname = env.url.replace(/^https?:\/\//, "");
            const offline = env.status === "offline";
            return (
              <div key={env.id} className={styles.card}>
                <div className={styles.top}>
                  <div>
                    <div className={styles.org}>{env.project_name}</div>
                    <div className={styles.project}>{env.environment_name}</div>
                  </div>
                  <KindBadge kind={env.kind} />
                </div>
                <div className={styles.meta}>
                  <StatusBadge status={env.status} />
                  {env.requires_app_auth && <AuthBadge />}
                </div>
                <div className={styles.footer}>
                  <span className={styles.hostname}>{hostname}</span>
                  <div className={styles.actions}>
                    <Link href={`/resource/${env.id}`} className={styles.btnSecondary}>
                      Détails
                    </Link>
                    {offline ? (
                      <span className={styles.btnDisabled}>Indisponible</span>
                    ) : (
                      <Link
                        href={env.requires_app_auth ? `/resource/${env.id}/interstitial` : `/resource/${env.id}`}
                        className={styles.btnPrimary}
                      >
                        Ouvrir ↗
                      </Link>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 3 : Vérifier la compilation**

```bash
cd apps/web && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4 : Commit**

```bash
git add apps/web/src/app/\(portal\)/client/
git commit -m "feat(web): E05 client page — sidebar + resources list"
```

---

## Task 8 : Frontend — E06 Resource detail page

**Files:**
- Modify: `apps/web/src/app/(portal)/resource/[id]/page.tsx`
- Create: `apps/web/src/app/(portal)/resource/[id]/resource.module.css`

Charge tous les envs, filtre par id. Affiche breadcrumb, méta-table, panneau de statut, bouton Ouvrir.

- [ ] **Step 1 : Créer `resource.module.css`**

```css
/* apps/web/src/app/(portal)/resource/[id]/resource.module.css */
.main {
  padding: 32px 36px;
  max-width: 1000px;
  margin: 0 auto;
}

.breadcrumb {
  font-size: 13px;
  color: var(--color-text-muted);
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.breadcrumb a {
  color: var(--color-primary);
  text-decoration: none;
  font-weight: 500;
}

.breadcrumb a:hover { text-decoration: underline; }

.breadcrumb span { color: var(--color-text-subtle); }

.layout {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 24px;
  align-items: start;
}

.title {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.4px;
  margin-bottom: 6px;
}

.desc {
  font-size: 14px;
  color: var(--color-text-muted);
  line-height: 1.6;
  margin-bottom: 18px;
}

.noticeOk {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 11px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.5;
  margin-bottom: 12px;
  background: var(--color-success-bg);
  color: var(--color-success);
}

.noticeWarn {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 11px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.5;
  margin-bottom: 12px;
  background: var(--color-warning-bg);
  color: var(--color-warning);
}

.metaTable {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
  margin-bottom: 20px;
}

.metaRow {
  display: flex;
  padding: 11px 16px;
  border-bottom: 1px solid var(--color-border);
  font-size: 13px;
}

.metaRow:last-child { border-bottom: none; }

.metaKey {
  width: 150px;
  flex-shrink: 0;
  color: var(--color-text-muted);
  font-weight: 500;
}

.metaVal { color: var(--color-text); }

.metaMono {
  font-family: monospace;
  font-size: 12px;
}

.actions {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}

.btnPrimary {
  font-family: var(--font);
  font-size: 13px;
  font-weight: 600;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  padding: 10px 20px;
  cursor: pointer;
  text-decoration: none;
  display: inline-block;
  transition: background 0.14s;
}

.btnPrimary:hover { background: var(--color-primary-h); }

.btnSecondary {
  font-family: var(--font);
  font-size: 13px;
  font-weight: 500;
  background: var(--color-surface-2);
  color: var(--color-text-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 9px 18px;
  cursor: pointer;
  text-decoration: none;
  display: inline-block;
}

/* Status panel */
.statusPanel {
  display: grid;
  gap: 11px;
}

.tile {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
}

.tileLabel {
  font-size: 10px;
  font-weight: 700;
  color: var(--color-text-subtle);
  text-transform: uppercase;
  letter-spacing: 0.07em;
  margin-bottom: 7px;
}

.tileValue {
  font-size: 14px;
  font-weight: 700;
}

.tileSub {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: 3px;
}

.colorOk     { color: var(--color-success); }
.colorWarn   { color: var(--color-warning); }
.colorMuted  { color: var(--color-text-muted); }

@media (max-width: 700px) {
  .layout { grid-template-columns: 1fr; }
  .main { padding: 20px 14px; }
}
```

- [ ] **Step 2 : Modifier `resource/[id]/page.tsx`**

```typescript
// apps/web/src/app/(portal)/resource/[id]/page.tsx
// E06 — Détail environnement
// Référence visuelle : docs/ds/mockups/devgate-e06-detail-env.mockup.html
// Note : upstream_hostname et service_token_ref ne sont JAMAIS renvoyés par l'API portal.
import Link from "next/link";
import { redirect, notFound } from "next/navigation";
import { serverPortalApi, ServerApiError } from "@/lib/api/server";
import { KindBadge, StatusBadge, AuthBadge } from "@/components/portal/Badge";
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
            {isOnline ? (
              <Link
                href={env.requires_app_auth ? `/resource/${id}/interstitial` : env.url}
                className={styles.btnPrimary}
                {...(!env.requires_app_auth ? { target: "_blank", rel: "noopener noreferrer" } : {})}
              >
                Ouvrir la ressource ↗
              </Link>
            ) : null}
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

- [ ] **Step 3 : Vérifier la compilation**

```bash
cd apps/web && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4 : Commit**

```bash
git add apps/web/src/app/\(portal\)/resource/\[id\]/page.tsx \
        apps/web/src/app/\(portal\)/resource/\[id\]/resource.module.css
git commit -m "feat(web): E06 resource detail — breadcrumb, meta table, status panel"
```

---

## Task 9 : Frontend — E07 Interstitiel double auth

**Files:**
- Modify: `apps/web/src/app/(portal)/resource/[id]/interstitial/page.tsx`
- Create: `apps/web/src/app/(portal)/resource/[id]/interstitial/interstitial.module.css`

Page d'avertissement avant l'ouverture d'une ressource qui demande une auth applicative.

- [ ] **Step 1 : Créer `interstitial.module.css`**

```css
/* apps/web/src/app/(portal)/resource/[id]/interstitial/interstitial.module.css */
.wrap {
  min-height: calc(100vh - 56px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  background:
    radial-gradient(ellipse 80% 60% at 60% -10%, rgba(37, 99, 235, 0.14) 0%, transparent 70%),
    radial-gradient(ellipse 60% 50% at -10% 80%, rgba(139, 92, 246, 0.09) 0%, transparent 60%),
    var(--color-bg);
}

.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  width: 100%;
  max-width: 500px;
  padding: 48px 40px 40px;
  text-align: center;
}

.icon {
  width: 68px;
  height: 68px;
  border-radius: 50%;
  background: #cffafe;
  margin: 0 auto 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
}

.title {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.3px;
  margin-bottom: 10px;
}

.sub {
  font-size: 14px;
  color: var(--color-text-muted);
  line-height: 1.6;
  margin-bottom: 22px;
  max-width: 36ch;
  margin-left: auto;
  margin-right: auto;
}

.notice {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.5;
  margin-bottom: 22px;
  text-align: left;
  background: #cffafe;
  color: #0891b2;
}

.btnPrimary {
  width: 100%;
  padding: 11px 20px;
  font-family: var(--font);
  font-size: 14px;
  font-weight: 600;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background 0.14s;
  margin-bottom: 10px;
  display: block;
  text-align: center;
  text-decoration: none;
  line-height: 1.5;
}

.btnPrimary:hover { background: var(--color-primary-h); }

.btnSecondary {
  width: 100%;
  padding: 10px 20px;
  font-family: var(--font);
  font-size: 14px;
  font-weight: 500;
  background: var(--color-surface-2);
  color: var(--color-text-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background 0.14s;
  display: block;
  text-align: center;
  text-decoration: none;
  line-height: 1.5;
}

.btnSecondary:hover { background: var(--color-border); color: var(--color-text); }

.note {
  margin-top: 16px;
  font-size: 12px;
  color: var(--color-text-subtle);
}
```

- [ ] **Step 2 : Modifier `interstitial/page.tsx`**

```typescript
// apps/web/src/app/(portal)/resource/[id]/interstitial/page.tsx
// E07 — Interstitiel double auth
// Référence visuelle : docs/ds/mockups/devgate-e07-interstitiel.mockup.html
// Affiché uniquement quand requires_app_auth=true, avant ouverture de la ressource.
// L'URL cible est l'URL publique de l'environnement — jamais un hostname Cloudflare brut.
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
          href={env.url}
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

- [ ] **Step 3 : Vérifier la compilation**

```bash
cd apps/web && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4 : Commit**

```bash
git add apps/web/src/app/\(portal\)/resource/\[id\]/interstitial/
git commit -m "feat(web): E07 interstitial double-auth page"
```

---

## Task 10 : Frontend — E12 Profile (ProfileClient + page)

**Files:**
- Create: `apps/web/src/app/(portal)/profile/ProfileClient.tsx`
- Create: `apps/web/src/app/(portal)/profile/ProfileClient.test.tsx`
- Create: `apps/web/src/app/(portal)/profile/profile.module.css`
- Modify: `apps/web/src/app/(portal)/profile/page.tsx`

- [ ] **Step 1 : Écrire le test ProfileClient**

```typescript
// apps/web/src/app/(portal)/profile/ProfileClient.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProfileClient } from "./ProfileClient";
import type { MeResponse, SessionItem } from "@/lib/api/server";

// Mock du client API
vi.mock("@/lib/api/client", () => ({
  portalApi: {
    revokeSession: vi.fn().mockResolvedValue(undefined),
  },
}));

const USER: MeResponse = {
  id: "u1",
  email: "alice@test.com",
  display_name: "Alice Test",
};

const SESSIONS: SessionItem[] = [
  {
    id: "s-current",
    expires_at: "2026-04-27T00:00:00Z",
    last_seen_at: "2026-04-20T10:00:00Z",
    ip: "127.0.0.1",
    user_agent: "Chrome/macOS",
    is_current: true,
  },
  {
    id: "s-other",
    expires_at: "2026-04-25T00:00:00Z",
    last_seen_at: "2026-04-19T08:00:00Z",
    ip: "10.0.0.1",
    user_agent: "Safari/iPhone",
    is_current: false,
  },
];

describe("ProfileClient", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders user name and email", () => {
    render(<ProfileClient user={USER} initialSessions={SESSIONS} />);
    expect(screen.getByText("Alice Test")).toBeInTheDocument();
    expect(screen.getByText("alice@test.com")).toBeInTheDocument();
  });

  it("renders all sessions", () => {
    render(<ProfileClient user={USER} initialSessions={SESSIONS} />);
    expect(screen.getByText("Chrome/macOS")).toBeInTheDocument();
    expect(screen.getByText("Safari/iPhone")).toBeInTheDocument();
  });

  it("current session revoke button is disabled", () => {
    render(<ProfileClient user={USER} initialSessions={SESSIONS} />);
    const buttons = screen.getAllByText("Révoquer");
    // Le bouton de la session courante est disabled
    const currentBtn = buttons.find((b) => b.closest("[data-current='true']"));
    expect(currentBtn).toBeDefined();
  });

  it("revoking a session calls the API", async () => {
    const { portalApi } = await import("@/lib/api/client");
    render(<ProfileClient user={USER} initialSessions={SESSIONS} />);

    const revokeButtons = screen.getAllByText("Révoquer");
    // Le seul bouton actif est pour s-other
    const activeRevoke = revokeButtons.find(
      (b) => !(b as HTMLButtonElement).disabled,
    )!;
    await userEvent.click(activeRevoke);

    await waitFor(() => {
      expect(portalApi.revokeSession).toHaveBeenCalledWith("s-other");
    });
  });

  it("shows avatar initials from display name", () => {
    render(<ProfileClient user={USER} initialSessions={SESSIONS} />);
    expect(screen.getByText("AT")).toBeInTheDocument(); // "Alice Test" → "AT"
  });
});
```

- [ ] **Step 2 : Lancer le test — vérifier qu'il échoue**

```bash
cd apps/web && npx vitest run src/app/\(portal\)/profile/ProfileClient.test.tsx
```

Expected: FAIL — cannot find module `./ProfileClient`.

- [ ] **Step 3 : Créer `profile.module.css`**

```css
/* apps/web/src/app/(portal)/profile/profile.module.css */
.main {
  padding: 32px 36px;
  max-width: 900px;
  margin: 0 auto;
}

.pageTitle {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.3px;
  margin-bottom: 3px;
}

.pageSub {
  font-size: 13px;
  color: var(--color-text-muted);
  margin-bottom: 24px;
}

.layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 24px;
  align-items: start;
}

/* Profile card */
.profileCard {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 28px;
  text-align: center;
}

.avatarLg {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 700;
  color: #fff;
  margin: 0 auto 14px;
}

.profileName {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 3px;
}

.profileEmail {
  font-size: 13px;
  color: var(--color-text-muted);
  margin-bottom: 14px;
}

.roleBadge {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 9px;
  border-radius: 20px;
  background: #cffafe;
  color: #0891b2;
}

.divider {
  height: 1px;
  background: var(--color-border);
  margin: 20px 0;
}

.fieldGroup { margin-bottom: 14px; text-align: left; }

.fieldLabel {
  display: block;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 5px;
}

.fieldInput {
  width: 100%;
  padding: 9px 12px;
  font-family: var(--font);
  font-size: 13px;
  background: var(--color-surface-2);
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text);
  outline: none;
  transition: border-color 0.14s;
}

.fieldInput:focus { border-color: var(--color-primary); }

.btnPrimary {
  width: 100%;
  padding: 10px 16px;
  font-family: var(--font);
  font-size: 13px;
  font-weight: 600;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background 0.14s;
  margin-bottom: 8px;
}

.btnPrimary:hover { background: var(--color-primary-h); }

.btnDanger {
  width: 100%;
  padding: 9px 16px;
  font-family: var(--font);
  font-size: 13px;
  font-weight: 500;
  background: none;
  color: var(--color-danger);
  border: 1px solid var(--color-danger);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background 0.14s;
}

.btnDanger:hover { background: var(--color-danger-bg); }

/* Sessions */
.sectionTitle {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 12px;
}

.sessions { display: flex; flex-direction: column; gap: 10px; }

.session {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.sessionCurrent { border-color: var(--color-primary); background: var(--color-primary-s); }

.curLabel {
  font-size: 10px;
  font-weight: 700;
  color: var(--color-primary);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 3px;
}

.sessionDevice { font-size: 13px; font-weight: 600; }

.sessionMeta {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

.btnRevoke {
  font-family: var(--font);
  font-size: 12px;
  font-weight: 500;
  color: var(--color-danger);
  background: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 4px 10px;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: background 0.12s, border-color 0.12s;
}

.btnRevoke:hover { background: var(--color-danger-bg); border-color: var(--color-danger); }

.btnRevoke:disabled { opacity: 0.35; cursor: not-allowed; pointer-events: none; }

.notice {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 11px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.5;
  margin-top: 14px;
  background: #cffafe;
  color: #0891b2;
}

@media (max-width: 700px) {
  .layout { grid-template-columns: 1fr; }
  .main { padding: 20px 14px; }
}
```

- [ ] **Step 4 : Créer `ProfileClient.tsx`**

```typescript
// apps/web/src/app/(portal)/profile/ProfileClient.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authApi, portalApi } from "@/lib/api/client";
import type { MeResponse, SessionItem } from "@/lib/api/server";
import styles from "./profile.module.css";

interface Props {
  user: MeResponse;
  initialSessions: SessionItem[];
}

function initials(user: MeResponse): string {
  const name = user.display_name ?? user.email;
  return name
    .split(/[\s@]/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join("");
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function daysUntil(iso: string): number {
  const ms = new Date(iso).getTime() - Date.now();
  return Math.max(0, Math.ceil(ms / 86_400_000));
}

export function ProfileClient({ user, initialSessions }: Props) {
  const router = useRouter();
  const [sessions, setSessions] = useState(initialSessions);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState(user.display_name ?? "");

  async function handleRevoke(sessionId: string) {
    setRevokingId(sessionId);
    try {
      await portalApi.revokeSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    } finally {
      setRevokingId(null);
    }
  }

  async function handleLogout() {
    await authApi.logout();
    router.push("/login");
  }

  return (
    <main className={styles.main}>
      <h1 className={styles.pageTitle}>Mon profil</h1>
      <p className={styles.pageSub}>Informations personnelles et sessions actives</p>

      <div className={styles.layout}>
        {/* Carte profil */}
        <div>
          <div className={styles.profileCard}>
            <div className={styles.avatarLg}>{initials(user)}</div>
            <div className={styles.profileName}>{user.display_name ?? user.email.split("@")[0]}</div>
            <div className={styles.profileEmail}>{user.email}</div>
            <span className={styles.roleBadge}>client_member</span>

            <div className={styles.divider} />

            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>Nom affiché</label>
              <input
                className={styles.fieldInput}
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Votre nom"
              />
            </div>
            <button className={styles.btnPrimary} type="button">
              Mettre à jour
            </button>
            <button className={styles.btnDanger} type="button" onClick={handleLogout}>
              Se déconnecter
            </button>
          </div>
        </div>

        {/* Sessions actives */}
        <div>
          <div className={styles.sectionTitle}>Sessions actives</div>
          <div className={styles.sessions}>
            {sessions.map((s) => (
              <div
                key={s.id}
                className={`${styles.session} ${s.is_current ? styles.sessionCurrent : ""}`}
                data-current={s.is_current}
              >
                <div>
                  {s.is_current && <div className={styles.curLabel}>Session actuelle</div>}
                  <div className={styles.sessionDevice}>
                    {s.user_agent ?? "Appareil inconnu"}
                  </div>
                  <div className={styles.sessionMeta}>
                    {s.ip ? `IP ${s.ip} · ` : ""}
                    Créée le {formatDate(s.last_seen_at)} · Expire dans {daysUntil(s.expires_at)} jour
                    {daysUntil(s.expires_at) !== 1 ? "s" : ""}
                  </div>
                </div>
                <button
                  className={styles.btnRevoke}
                  type="button"
                  disabled={s.is_current || revokingId === s.id}
                  onClick={() => handleRevoke(s.id)}
                >
                  {revokingId === s.id ? "…" : "Révoquer"}
                </button>
              </div>
            ))}
          </div>
          <div className={styles.notice}>
            ℹ️ Chaque session est valide 7 jours. La révocation est immédiate.
          </div>
        </div>
      </div>
    </main>
  );
}
```

- [ ] **Step 5 : Modifier `profile/page.tsx`**

```typescript
// apps/web/src/app/(portal)/profile/page.tsx
// E12 — Profil / sessions actives
// Référence visuelle : docs/ds/mockups/devgate-e12-profile.mockup.html
import { redirect } from "next/navigation";
import { serverPortalApi, ServerApiError } from "@/lib/api/server";
import { ProfileClient } from "./ProfileClient";

export default async function ProfilePage() {
  let user;
  let sessions;

  try {
    [user, sessions] = await Promise.all([
      serverPortalApi.me(),
      serverPortalApi.sessions(),
    ]);
  } catch (err) {
    if (err instanceof ServerApiError && err.status === 401) {
      redirect("/login");
    }
    redirect("/session-expired");
  }

  return <ProfileClient user={user} initialSessions={sessions} />;
}
```

- [ ] **Step 6 : Lancer les tests**

```bash
cd apps/web && npx vitest run src/app/\(portal\)/profile/ProfileClient.test.tsx
```

Expected: 5 tests PASSED.

- [ ] **Step 7 : Lancer tous les tests frontend**

```bash
cd apps/web && npx vitest run
```

Expected: tous les tests passent (badge 7 + envCard 7 + portalDashboard 6 + profileClient 5 + tests antérieurs).

- [ ] **Step 8 : Lancer tous les tests backend**

```bash
cd apps/api && python -m pytest tests/ -v
```

Expected: tous les tests passent.

- [ ] **Step 9 : Commit**

```bash
git add apps/web/src/app/\(portal\)/profile/
git commit -m "feat(web): E12 profile page — sessions list with revoke"
```

---

## Vérification finale manuelle

Avec `docker compose up` (ou les services locaux) :

1. Aller sur `http://localhost:3000/login` → saisir votre email → recevoir le magic link dans Mailpit (`http://localhost:8125`) → cliquer → être redirigé sur `/portal`
2. **E04** : vérifier le banner de bienvenue avec votre prénom, les env cards avec badges kind/status, le filtre par kind et la recherche
3. **E05** : cliquer sur une card → atterrir sur `/client/[slug]` → vérifier sidebar + liste
4. **E06** : cliquer "Détails" → vérifier breadcrumb, meta-table, panneau statut
5. **E07** : cliquer "Ouvrir ↗" sur un env avec `requires_app_auth=true` → vérifier la page interstitielle → "Continuer" ouvre l'URL en nouvel onglet
6. **E12** : cliquer "Mon profil" → vérifier sessions, révoquer une session secondaire

---

## Self-Review

### Spec coverage
- [x] E04 — welcome banner + env grid + filtre ✓ (Task 6)
- [x] E05 — sidebar clients + resource list ✓ (Task 7)
- [x] E06 — breadcrumb + meta table + status panel ✓ (Task 8)
- [x] E07 — interstitiel double auth ✓ (Task 9)
- [x] E08 — état vide (intégré dans PortalDashboard) ✓ (Task 6)
- [x] E12 — profil + sessions + révocation ✓ (Task 10)
- [x] Backend portal router coverage ✓ (Task 1)
- [x] PortalHeader avec user data réel ✓ (Task 5)
- [x] Server-side API helper ✓ (Task 2)

### Règles architecture respectées
- Aucun `upstream_hostname`, `cloudflare_tunnel_id`, `service_token_ref` ne passe par le frontend
- Le frontend ne déduit pas les permissions — il affiche ce que le backend renvoie
- Cookie session jamais lu côté client (seul `server.ts` lit les cookies via `next/headers`)
- `LogoutButton` appelle `/auth/logout` → redirect → le cookie est supprimé côté serveur
