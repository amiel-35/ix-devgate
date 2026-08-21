# Back-office Agence v1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permettre à un admin agence de gérer clients (orgs), projets, environnements, accès (grants) et de consulter l'audit, sans intervention directe en base.

**Architecture:** Server Components chargent les données via `serverAdminApi` (cookie forwarding), Client Components gèrent les interactions (création, révocation). Le backend vérifie le rôle `agency_admin` sur chaque route `/admin/*`. Le frontend ne déduit aucune permission.

**Tech Stack:** FastAPI + SQLAlchemy (backend), Next.js 15 App Router + CSS Modules (frontend), Vitest + pytest + SQLite in-memory (tests).

---

## File Map

**Backend — nouveaux fichiers / modifiés :**
- Modify: `apps/api/app/modules/admin/router.py` — ajouter projets CRUD, enrichir listes, stats
- Modify: `apps/api/app/modules/admin/schemas.py` — ajouter `CreateProjectRequest`, `StatsResponse`
- Create: `apps/api/tests/integration/test_admin_router.py`

**Frontend — nouveaux fichiers / modifiés :**
- Create: `apps/web/src/lib/api/server-admin.ts` — serverAdminApi (Server Components)
- Modify: `apps/web/src/lib/api/client.ts` — typer adminApi
- Modify: `apps/web/src/app/(admin)/layout.tsx` — layout réel avec sidebar
- Create: `apps/web/src/components/admin/AdminSidebar.tsx`
- Create: `apps/web/src/components/admin/AdminSidebar.module.css`
- Modify: `apps/web/src/app/(admin)/admin/page.tsx` — Dashboard stats + audit récent
- Create: `apps/web/src/app/(admin)/admin/admin.module.css`
- Modify: `apps/web/src/app/(admin)/admin/clients/page.tsx` — liste + create
- Create: `apps/web/src/app/(admin)/admin/clients/ClientsClient.tsx`
- Create: `apps/web/src/app/(admin)/admin/clients/clients.module.css`
- Modify: `apps/web/src/app/(admin)/admin/environments/page.tsx` — liste + create
- Create: `apps/web/src/app/(admin)/admin/environments/EnvironmentsClient.tsx`
- Create: `apps/web/src/app/(admin)/admin/environments/environments.module.css`
- Modify: `apps/web/src/app/(admin)/admin/access/page.tsx` — liste + grant + revoke
- Create: `apps/web/src/app/(admin)/admin/access/AccessClient.tsx`
- Create: `apps/web/src/app/(admin)/admin/access/access.module.css`
- Modify: `apps/web/src/app/(admin)/admin/audit/page.tsx` — liste + filtre type
- Create: `apps/web/src/app/(admin)/admin/audit/AuditClient.tsx`
- Create: `apps/web/src/app/(admin)/admin/audit/audit.module.css`

---

## Task 1: Backend — Projects CRUD + enrichissement des listes + stats

**Files:**
- Modify: `apps/api/app/modules/admin/schemas.py`
- Modify: `apps/api/app/modules/admin/router.py`

- [ ] **Step 1 : Ajouter les nouveaux schémas Pydantic**

Remplacer tout le contenu de `apps/api/app/modules/admin/schemas.py` :

```python
from pydantic import BaseModel, EmailStr


class CreateOrganizationRequest(BaseModel):
    name: str
    slug: str
    branding_name: str | None = None
    support_email: str | None = None


class CreateProjectRequest(BaseModel):
    organization_id: str
    name: str
    slug: str


class CreateEnvironmentRequest(BaseModel):
    project_id: str
    name: str
    slug: str
    kind: str  # dev | staging | preview | internal
    public_hostname: str
    upstream_hostname: str | None = None
    cloudflare_tunnel_id: str | None = None
    cloudflare_access_app_id: str | None = None
    service_token_ref: str | None = None
    requires_app_auth: bool = False


class CreateAccessGrantRequest(BaseModel):
    email: EmailStr
    organization_id: str
    role: str  # client_member | reviewer | agency_admin
    display_name: str | None = None


class AuditEventResponse(BaseModel):
    id: str
    actor_user_id: str | None
    event_type: str
    target_type: str | None
    target_id: str | None
    metadata_json: dict | None
    created_at: str


class StatsResponse(BaseModel):
    active_orgs: int
    active_envs: int
    active_users: int
    events_today: int
```

- [ ] **Step 2 : Réécrire le router admin avec projets + enrichissement + stats**

Remplacer tout le contenu de `apps/api/app/modules/admin/router.py` :

```python
"""
Back-office agence — CRUD clients, projets, environnements, accès, audit, stats.
Toutes les routes exigent agency_admin.
"""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.modules.admin.schemas import (
    AuditEventResponse,
    CreateAccessGrantRequest,
    CreateEnvironmentRequest,
    CreateOrganizationRequest,
    CreateProjectRequest,
    StatsResponse,
)
from app.modules.audit.service import audit
from app.shared.deps import require_agency_admin
from app.shared.exceptions import NotFoundException
from app.shared.models import (
    AccessGrant,
    AuditEvent,
    Environment,
    Organization,
    Project,
    User,
)

router = APIRouter(dependencies=[Depends(require_agency_admin)])


# ── Stats ─────────────────────────────────────────────────────────

@router.get("/stats", response_model=StatsResponse)
def get_stats(db: DbSession = Depends(get_db)):
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
    return StatsResponse(
        active_orgs=db.query(Organization).count(),
        active_envs=db.query(Environment).filter(Environment.status == "active").count(),
        active_users=db.query(User).filter(User.status == "active").count(),
        events_today=db.query(AuditEvent).filter(AuditEvent.created_at >= today_start).count(),
    )


# ── Organisations ─────────────────────────────────────────────────

@router.get("/organizations")
def list_organizations(db: DbSession = Depends(get_db)):
    orgs = db.query(Organization).all()
    result = []
    for org in orgs:
        env_count = (
            db.query(Environment)
            .join(Project)
            .filter(Project.organization_id == org.id)
            .count()
        )
        user_count = (
            db.query(AccessGrant)
            .filter(
                AccessGrant.organization_id == org.id,
                AccessGrant.revoked_at.is_(None),
            )
            .count()
        )
        result.append({
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "branding_name": org.branding_name,
            "support_email": org.support_email,
            "env_count": env_count,
            "user_count": user_count,
        })
    return result


@router.post("/organizations", status_code=201)
def create_organization(
    body: CreateOrganizationRequest,
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    org = Organization(**body.model_dump())
    db.add(org)
    db.commit()
    audit(db, actor_user_id=admin.id, event_type="admin.organization.created",
          target_type="organization", target_id=org.id)
    db.commit()
    return {"id": org.id}


# ── Projets ───────────────────────────────────────────────────────

@router.get("/projects")
def list_projects(org_id: str | None = None, db: DbSession = Depends(get_db)):
    q = db.query(Project)
    if org_id:
        q = q.filter(Project.organization_id == org_id)
    return [
        {"id": p.id, "organization_id": p.organization_id, "name": p.name, "slug": p.slug}
        for p in q.all()
    ]


@router.post("/projects", status_code=201)
def create_project(
    body: CreateProjectRequest,
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    org = db.query(Organization).filter(Organization.id == body.organization_id).first()
    if not org:
        raise NotFoundException()
    project = Project(**body.model_dump())
    db.add(project)
    db.commit()
    audit(db, actor_user_id=admin.id, event_type="admin.project.created",
          target_type="project", target_id=project.id)
    db.commit()
    return {"id": project.id}


# ── Environnements ────────────────────────────────────────────────

@router.get("/environments")
def list_environments(db: DbSession = Depends(get_db)):
    envs = db.query(Environment).join(Project).join(Organization).all()
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
            "cloudflare_access_app_id": e.cloudflare_access_app_id,
            "org_name": e.project.organization.name,
            "project_name": e.project.name,
        }
        for e in envs
    ]


@router.post("/environments", status_code=201)
def create_environment(
    body: CreateEnvironmentRequest,
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    project = db.query(Project).filter(Project.id == body.project_id).first()
    if not project:
        raise NotFoundException()
    env = Environment(**body.model_dump())
    db.add(env)
    db.commit()
    audit(db, actor_user_id=admin.id, event_type="admin.environment.created",
          target_type="environment", target_id=env.id)
    db.commit()
    return {"id": env.id}


# ── Accès (grants) ────────────────────────────────────────────────

@router.get("/access-grants")
def list_grants(db: DbSession = Depends(get_db)):
    grants = db.query(AccessGrant).all()
    return [
        {
            "id": g.id,
            "user_id": g.user_id,
            "user_email": g.user.email,
            "organization_id": g.organization_id,
            "org_name": g.organization.name,
            "role": g.role,
            "created_at": g.created_at.isoformat(),
            "revoked_at": g.revoked_at.isoformat() if g.revoked_at else None,
        }
        for g in grants
    ]


@router.post("/access-grants", status_code=201)
def create_grant(
    body: CreateAccessGrantRequest,
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        user = User(email=body.email, display_name=body.display_name, kind="client")
        db.add(user)
        db.flush()

    grant = AccessGrant(user_id=user.id, organization_id=body.organization_id, role=body.role)
    db.add(grant)
    db.commit()
    audit(db, actor_user_id=admin.id, event_type="admin.access_grant.created",
          target_type="access_grant", target_id=grant.id,
          metadata={"email": body.email, "role": body.role})
    db.commit()
    return {"id": grant.id}


@router.delete("/access-grants/{grant_id}", status_code=204)
def revoke_grant(
    grant_id: str,
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    grant = db.query(AccessGrant).filter(AccessGrant.id == grant_id).first()
    if not grant:
        raise NotFoundException()
    grant.revoked_at = datetime.now(tz=timezone.utc)
    db.commit()
    audit(db, actor_user_id=admin.id, event_type="admin.access_grant.revoked",
          target_type="access_grant", target_id=grant_id)
    db.commit()


# ── Audit ─────────────────────────────────────────────────────────

@router.get("/audit-events", response_model=list[AuditEventResponse])
def list_audit_events(
    limit: int = 50,
    offset: int = 0,
    db: DbSession = Depends(get_db),
):
    events = (
        db.query(AuditEvent)
        .order_by(AuditEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        AuditEventResponse(
            id=e.id,
            actor_user_id=e.actor_user_id,
            event_type=e.event_type,
            target_type=e.target_type,
            target_id=e.target_id,
            metadata_json=e.metadata_json,
            created_at=e.created_at.isoformat(),
        )
        for e in events
    ]
```

- [ ] **Step 3 : Vérifier la syntaxe Python**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/python -c "from apps.api.app.modules.admin import router, schemas; print('OK')"
```

Si erreur d'import, vérifier depuis le container :

```bash
docker compose exec api python -c "from app.modules.admin import router, schemas; print('OK')"
```

Expected: `OK`

- [ ] **Step 4 : Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/api/app/modules/admin/router.py apps/api/app/modules/admin/schemas.py
git commit -m "feat(admin): projets CRUD + enrichissement listes + stats endpoint"
```

---

## Task 2: Backend — Tests d'intégration admin

**Files:**
- Create: `apps/api/tests/integration/test_admin_router.py`

- [ ] **Step 1 : Écrire les tests**

Créer `apps/api/tests/integration/test_admin_router.py` :

```python
"""Tests d'intégration — routes /admin/*"""
from datetime import datetime, timedelta, timezone

from app.shared.models import (
    AccessGrant,
    AuditEvent,
    Environment,
    Organization,
    Project,
    Session as SessionModel,
    User,
)


# ── Helpers ───────────────────────────────────────────────────────

def _make_admin(db_session, session_id="s-admin"):
    admin = User(
        id="admin-1",
        email="admin@agency.com",
        display_name="Admin Agence",
        kind="agency",
        status="active",
    )
    db_session.add(admin)
    session = SessionModel(
        id=session_id,
        user_id="admin-1",
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=7),
    )
    db_session.add(session)
    db_session.commit()
    return admin


def _make_org(db_session, org_id="org-1", name="Client X", slug="client-x"):
    org = Organization(id=org_id, name=name, slug=slug)
    db_session.add(org)
    db_session.commit()
    return org


def _make_project(db_session, proj_id="proj-1", org_id="org-1"):
    p = Project(id=proj_id, organization_id=org_id, name="Refonte", slug="refonte")
    db_session.add(p)
    db_session.commit()
    return p


def _make_env(db_session, env_id="env-1", proj_id="proj-1"):
    e = Environment(
        id=env_id,
        project_id=proj_id,
        name="Staging",
        slug="staging",
        kind="staging",
        public_hostname="staging.example.com",
        status="active",
    )
    db_session.add(e)
    db_session.commit()
    return e


def _auth(client, session_id="s-admin"):
    client.cookies.set("devgate_session", session_id)


# ── GET /admin/stats ──────────────────────────────────────────────

def test_stats_empty(client, db_session):
    _make_admin(db_session)
    _auth(client)
    r = client.get("/admin/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["active_orgs"] == 0
    assert data["active_envs"] == 0
    assert data["active_users"] == 1  # l'admin lui-même
    assert data["events_today"] >= 0


def test_stats_counts(client, db_session):
    _make_admin(db_session)
    _auth(client)
    org = _make_org(db_session)
    proj = _make_project(db_session)
    _make_env(db_session)

    r = client.get("/admin/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["active_orgs"] == 1
    assert data["active_envs"] == 1


# ── GET /admin/organizations ──────────────────────────────────────

def test_list_orgs_empty(client, db_session):
    _make_admin(db_session)
    _auth(client)
    r = client.get("/admin/organizations")
    assert r.status_code == 200
    assert r.json() == []


def test_list_orgs_with_counts(client, db_session):
    _make_admin(db_session)
    _auth(client)
    org = _make_org(db_session)
    proj = _make_project(db_session)
    _make_env(db_session)

    r = client.get("/admin/organizations")
    assert r.status_code == 200
    orgs = r.json()
    assert len(orgs) == 1
    assert orgs[0]["name"] == "Client X"
    assert orgs[0]["env_count"] == 1
    assert orgs[0]["user_count"] == 0


# ── POST /admin/organizations ─────────────────────────────────────

def test_create_org(client, db_session):
    _make_admin(db_session)
    _auth(client)
    r = client.post("/admin/organizations", json={"name": "Nouveau Client", "slug": "nouveau"})
    assert r.status_code == 201
    assert "id" in r.json()


def test_create_org_requires_auth(client, db_session):
    r = client.post("/admin/organizations", json={"name": "X", "slug": "x"})
    assert r.status_code == 401


# ── GET /admin/projects ───────────────────────────────────────────

def test_list_projects_filtered(client, db_session):
    _make_admin(db_session)
    _auth(client)
    _make_org(db_session)
    _make_project(db_session)

    r = client.get("/admin/projects?org_id=org-1")
    assert r.status_code == 200
    projects = r.json()
    assert len(projects) == 1
    assert projects[0]["name"] == "Refonte"


def test_create_project(client, db_session):
    _make_admin(db_session)
    _auth(client)
    _make_org(db_session)

    r = client.post("/admin/projects", json={
        "organization_id": "org-1",
        "name": "Nouveau projet",
        "slug": "nouveau-projet",
    })
    assert r.status_code == 201
    assert "id" in r.json()


def test_create_project_unknown_org(client, db_session):
    _make_admin(db_session)
    _auth(client)
    r = client.post("/admin/projects", json={
        "organization_id": "unknown",
        "name": "X",
        "slug": "x",
    })
    assert r.status_code == 404


# ── GET /admin/environments ───────────────────────────────────────

def test_list_envs_enriched(client, db_session):
    _make_admin(db_session)
    _auth(client)
    _make_org(db_session)
    _make_project(db_session)
    _make_env(db_session)

    r = client.get("/admin/environments")
    assert r.status_code == 200
    envs = r.json()
    assert len(envs) == 1
    assert envs[0]["org_name"] == "Client X"
    assert envs[0]["project_name"] == "Refonte"
    assert "upstream_hostname" not in envs[0]
    assert "service_token_ref" not in envs[0]


# ── POST /admin/environments ──────────────────────────────────────

def test_create_env(client, db_session):
    _make_admin(db_session)
    _auth(client)
    _make_org(db_session)
    _make_project(db_session)

    r = client.post("/admin/environments", json={
        "project_id": "proj-1",
        "name": "Production",
        "slug": "production",
        "kind": "staging",
        "public_hostname": "prod.example.com",
    })
    assert r.status_code == 201
    assert "id" in r.json()


def test_create_env_unknown_project(client, db_session):
    _make_admin(db_session)
    _auth(client)
    r = client.post("/admin/environments", json={
        "project_id": "unknown",
        "name": "X",
        "slug": "x",
        "kind": "dev",
        "public_hostname": "x.example.com",
    })
    assert r.status_code == 404


# ── GET /admin/access-grants ──────────────────────────────────────

def test_list_grants_enriched(client, db_session):
    _make_admin(db_session)
    _auth(client)
    org = _make_org(db_session)

    # Créer un utilisateur + grant
    user = User(id="u-client", email="client@test.com", kind="client", status="active")
    db_session.add(user)
    grant = AccessGrant(
        id="grant-1",
        user_id="u-client",
        organization_id="org-1",
        role="client_member",
    )
    db_session.add(grant)
    db_session.commit()

    r = client.get("/admin/access-grants")
    assert r.status_code == 200
    grants = r.json()
    assert len(grants) == 1
    assert grants[0]["user_email"] == "client@test.com"
    assert grants[0]["org_name"] == "Client X"
    assert grants[0]["revoked_at"] is None


# ── POST /admin/access-grants ─────────────────────────────────────

def test_create_grant_creates_user_if_missing(client, db_session):
    _make_admin(db_session)
    _auth(client)
    _make_org(db_session)

    r = client.post("/admin/access-grants", json={
        "email": "nouveau@client.com",
        "organization_id": "org-1",
        "role": "client_member",
    })
    assert r.status_code == 201


# ── DELETE /admin/access-grants/{id} ─────────────────────────────

def test_revoke_grant(client, db_session):
    _make_admin(db_session)
    _auth(client)
    _make_org(db_session)

    user = User(id="u-client", email="client@test.com", kind="client", status="active")
    db_session.add(user)
    grant = AccessGrant(id="grant-1", user_id="u-client", organization_id="org-1", role="client_member")
    db_session.add(grant)
    db_session.commit()

    r = client.delete("/admin/access-grants/grant-1")
    assert r.status_code == 204

    db_session.refresh(grant)
    assert grant.revoked_at is not None


def test_revoke_grant_not_found(client, db_session):
    _make_admin(db_session)
    _auth(client)
    r = client.delete("/admin/access-grants/unknown")
    assert r.status_code == 404


# ── GET /admin/audit-events ───────────────────────────────────────

def test_list_audit_events(client, db_session):
    _make_admin(db_session)
    _auth(client)

    evt = AuditEvent(
        id="evt-1",
        event_type="admin.organization.created",
        actor_user_id="admin-1",
    )
    db_session.add(evt)
    db_session.commit()

    r = client.get("/admin/audit-events")
    assert r.status_code == 200
    events = r.json()
    assert len(events) >= 1
    assert events[0]["event_type"] == "admin.organization.created"
```

- [ ] **Step 2 : Lancer les tests et vérifier qu'ils passent**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/integration/test_admin_router.py -v 2>&1 | tail -30
```

Expected: tous les tests `PASSED` (≥ 16 tests).

- [ ] **Step 3 : Commit**

```bash
git add apps/api/tests/integration/test_admin_router.py
git commit -m "test(admin): tests d'intégration routes /admin/* (projets, stats, enrichissement)"
```

---

## Task 3: Frontend — serverAdminApi + typage du client adminApi

**Files:**
- Create: `apps/web/src/lib/api/server-admin.ts`
- Modify: `apps/web/src/lib/api/client.ts`

- [ ] **Step 1 : Créer `apps/web/src/lib/api/server-admin.ts`**

```typescript
// Helper pour appeler les routes /admin/* depuis les Server Components.
// Mêmes conventions que server.ts : forwarding du cookie devgate_session.
// Les routes admin retournent 403 si le rôle n'est pas agency_admin.

import { cookies } from "next/headers";

const API_BASE =
  process.env.API_INTERNAL_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8001";

export class AdminApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "AdminApiError";
  }
}

async function adminRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
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
    cache: "no-store",
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new AdminApiError(res.status, body.detail ?? res.statusText);
  }

  return res.json() as Promise<T>;
}

// ── Types ─────────────────────────────────────────────────────────

export type OrgItem = {
  id: string;
  name: string;
  slug: string;
  branding_name: string | null;
  support_email: string | null;
  env_count: number;
  user_count: number;
};

export type ProjectItem = {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
};

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
  cloudflare_access_app_id: string | null;
  org_name: string;
  project_name: string;
};

export type GrantItem = {
  id: string;
  user_id: string;
  user_email: string;
  organization_id: string;
  org_name: string;
  role: string;
  created_at: string;
  revoked_at: string | null;
};

export type AdminAuditEvent = {
  id: string;
  actor_user_id: string | null;
  event_type: string;
  target_type: string | null;
  target_id: string | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
};

export type StatsResponse = {
  active_orgs: number;
  active_envs: number;
  active_users: number;
  events_today: number;
};

// ── API Admin (server-side) ───────────────────────────────────────

export const serverAdminApi = {
  stats: () => adminRequest<StatsResponse>("/admin/stats"),
  organizations: () => adminRequest<OrgItem[]>("/admin/organizations"),
  projects: (orgId?: string) =>
    adminRequest<ProjectItem[]>(`/admin/projects${orgId ? `?org_id=${orgId}` : ""}`),
  environments: () => adminRequest<AdminEnvItem[]>("/admin/environments"),
  grants: () => adminRequest<GrantItem[]>("/admin/access-grants"),
  auditEvents: (limit = 50, offset = 0) =>
    adminRequest<AdminAuditEvent[]>(`/admin/audit-events?limit=${limit}&offset=${offset}`),
};
```

- [ ] **Step 2 : Typer `adminApi` dans `apps/web/src/lib/api/client.ts`**

Remplacer la section `adminApi` dans le fichier existant (garder tout le reste intact). Remplacer à partir de `// ── Admin ─────────────────────────────────────────────────────────` jusqu'à la fin :

```typescript
// ── Admin ────────────────────────────────────────────────────────

export type AdminCreateOrgPayload = { name: string; slug: string; branding_name?: string; support_email?: string };
export type AdminCreateProjectPayload = { organization_id: string; name: string; slug: string };
export type AdminCreateEnvPayload = {
  project_id: string; name: string; slug: string; kind: string;
  public_hostname: string; upstream_hostname?: string;
  cloudflare_tunnel_id?: string; cloudflare_access_app_id?: string;
  service_token_ref?: string; requires_app_auth?: boolean;
};
export type AdminCreateGrantPayload = { email: string; organization_id: string; role: string; display_name?: string };

export const adminApi = {
  organizations: {
    list: () => request<unknown[]>("/admin/organizations"),
    create: (data: AdminCreateOrgPayload) =>
      request<{ id: string }>("/admin/organizations", { method: "POST", body: JSON.stringify(data) }),
  },
  projects: {
    list: (orgId?: string) =>
      request<unknown[]>(`/admin/projects${orgId ? `?org_id=${orgId}` : ""}`),
    create: (data: AdminCreateProjectPayload) =>
      request<{ id: string }>("/admin/projects", { method: "POST", body: JSON.stringify(data) }),
  },
  environments: {
    list: () => request<unknown[]>("/admin/environments"),
    create: (data: AdminCreateEnvPayload) =>
      request<{ id: string }>("/admin/environments", { method: "POST", body: JSON.stringify(data) }),
  },
  grants: {
    list: () => request<unknown[]>("/admin/access-grants"),
    create: (data: AdminCreateGrantPayload) =>
      request<{ id: string }>("/admin/access-grants", { method: "POST", body: JSON.stringify(data) }),
    revoke: (id: string) =>
      request<void>(`/admin/access-grants/${id}`, { method: "DELETE" }),
  },
  audit: {
    list: (params?: { limit?: number; offset?: number }) => {
      const qs = new URLSearchParams(
        Object.entries(params ?? {}).map(([k, v]) => [k, String(v)]),
      ).toString();
      return request<unknown[]>(`/admin/audit-events${qs ? `?${qs}` : ""}`);
    },
  },
};

export { ApiError };
```

- [ ] **Step 3 : Vérifier la compilation TypeScript**

```bash
cd /Users/amiellavon/Sites/Captive-serveur/apps/web
npx tsc --noEmit 2>&1 | head -20
```

Expected: aucune erreur. Si erreurs, corriger avant de continuer.

- [ ] **Step 4 : Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/web/src/lib/api/server-admin.ts apps/web/src/lib/api/client.ts
git commit -m "feat(admin): serverAdminApi server-side + typage adminApi client"
```

---

## Task 4: Frontend — AdminLayout avec sidebar

**Files:**
- Create: `apps/web/src/components/admin/AdminSidebar.tsx`
- Create: `apps/web/src/components/admin/AdminSidebar.module.css`
- Modify: `apps/web/src/app/(admin)/layout.tsx`

- [ ] **Step 1 : Créer `apps/web/src/components/admin/AdminSidebar.tsx`**

```typescript
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./AdminSidebar.module.css";

const NAV = [
  { href: "/admin", label: "Dashboard", icon: "⊞", exact: true },
  { href: "/admin/clients", label: "Clients", icon: "🏢", exact: false },
  { href: "/admin/environments", label: "Environnements", icon: "🌐", exact: false },
  { href: "/admin/access", label: "Accès", icon: "🔑", exact: false },
  { href: "/admin/audit", label: "Audit", icon: "📋", exact: false },
];

export function AdminSidebar() {
  const pathname = usePathname();

  return (
    <aside className={styles.sidebar}>
      <div className={styles.brand}>
        <div className={styles.logo}>AG</div>
        <div>
          <div className={styles.brandName}>DevGate</div>
          <div className={styles.brandSub}>Back-office</div>
        </div>
      </div>

      <nav className={styles.nav}>
        {NAV.map(({ href, label, icon, exact }) => {
          const active = exact ? pathname === href : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`${styles.navItem} ${active ? styles.navItemActive : ""}`}
            >
              <span className={styles.navIcon}>{icon}</span>
              {label}
            </Link>
          );
        })}
      </nav>

      <div className={styles.footer}>
        <div className={styles.footerBadge}>Agence admin</div>
      </div>
    </aside>
  );
}
```

- [ ] **Step 2 : Créer `apps/web/src/components/admin/AdminSidebar.module.css`**

```css
.sidebar {
  width: 220px;
  min-width: 220px;
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 18px 16px;
  border-bottom: 1px solid var(--color-border);
}

.logo {
  width: 34px;
  height: 34px;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, var(--color-primary), #7c3aed);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.brandName {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: -0.2px;
  color: var(--color-text);
}

.brandSub {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-top: 1px;
}

.nav {
  flex: 1;
  padding: 10px 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.navItem {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  font-size: 13.5px;
  font-weight: 500;
  color: var(--color-text-muted);
  text-decoration: none;
  transition: background 0.12s, color 0.12s;
}

.navItem:hover {
  background: var(--color-surface-2);
  color: var(--color-text);
}

.navItemActive {
  background: var(--color-primary-s);
  color: var(--color-primary);
}

.navIcon {
  font-size: 15px;
  width: 18px;
  text-align: center;
}

.footer {
  padding: 14px 16px;
  border-top: 1px solid var(--color-border);
}

.footerBadge {
  font-size: 11px;
  color: var(--color-text-subtle);
  background: var(--color-surface-2);
  border-radius: var(--radius-sm);
  padding: 4px 8px;
  display: inline-block;
}
```

- [ ] **Step 3 : Mettre à jour `apps/web/src/app/(admin)/layout.tsx`**

```typescript
// Layout back-office agence
// Vérifie la session + rôle agency_admin côté backend (403 → /access-denied)
import { redirect } from "next/navigation";
import { requireAdminSession } from "@/lib/auth/session";
import { serverAdminApi, AdminApiError } from "@/lib/api/server-admin";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import type { ReactNode } from "react";

export default async function AdminLayout({ children }: { children: ReactNode }) {
  await requireAdminSession();

  // Vérification du rôle : si 403, l'utilisateur n'est pas agency_admin
  try {
    await serverAdminApi.stats();
  } catch (err) {
    if (err instanceof AdminApiError && err.status === 401) redirect("/login");
    if (err instanceof AdminApiError && err.status === 403) redirect("/access-denied");
    // Autre erreur : on laisse passer (API peut être momentanément indisponible)
  }

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "var(--color-bg)" }}>
      <AdminSidebar />
      <main style={{ flex: 1, overflow: "auto" }}>{children}</main>
    </div>
  );
}
```

- [ ] **Step 4 : Vérifier la compilation TypeScript**

```bash
cd /Users/amiellavon/Sites/Captive-serveur/apps/web
npx tsc --noEmit 2>&1 | head -20
```

Expected: aucune erreur.

- [ ] **Step 5 : Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/web/src/components/admin/ apps/web/src/app/\(admin\)/layout.tsx
git commit -m "feat(admin): AdminLayout avec sidebar navigation"
```

---

## Task 5: Frontend — Dashboard page

**Files:**
- Modify: `apps/web/src/app/(admin)/admin/page.tsx`
- Create: `apps/web/src/app/(admin)/admin/admin.module.css`

- [ ] **Step 1 : Créer `apps/web/src/app/(admin)/admin/admin.module.css`**

```css
.page {
  padding: 32px 36px;
  max-width: 1100px;
}

.pageTitle {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.3px;
  margin-bottom: 2px;
}

.pageSub {
  font-size: 13px;
  color: var(--color-text-muted);
  margin-bottom: 28px;
}

/* Stat cards */
.statsGrid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

.statCard {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 20px;
}

.statLabel {
  font-size: 12px;
  color: var(--color-text-muted);
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.statValue {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -1px;
  color: var(--color-text);
}

/* Section */
.sectionTitle {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 14px;
  color: var(--color-text);
}

/* Table */
.table {
  width: 100%;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  border-collapse: collapse;
  overflow: hidden;
}

.table th {
  text-align: left;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.4px;
  padding: 10px 16px;
  background: var(--color-surface-2);
  border-bottom: 1px solid var(--color-border);
}

.table td {
  padding: 10px 16px;
  font-size: 13px;
  border-bottom: 1px solid var(--color-border);
  vertical-align: middle;
}

.table tr:last-child td {
  border-bottom: none;
}

/* Badges */
.eventType {
  font-size: 11px;
  font-weight: 600;
  font-family: monospace;
  padding: 2px 7px;
  border-radius: var(--radius-sm);
  background: var(--color-surface-2);
  color: var(--color-text-muted);
}

/* Inline form */
.formRow {
  display: flex;
  gap: 10px;
  align-items: flex-end;
  margin-bottom: 20px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  flex: 1;
}

.label {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-muted);
}

.input {
  height: 36px;
  padding: 0 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  background: var(--color-surface);
  color: var(--color-text);
  width: 100%;
}

.input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.select {
  height: 36px;
  padding: 0 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  background: var(--color-surface);
  color: var(--color-text);
  width: 100%;
}

.btnPrimary {
  height: 36px;
  padding: 0 16px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
}

.btnPrimary:hover { background: var(--color-primary-h); }
.btnPrimary:disabled { opacity: 0.55; cursor: not-allowed; }

.btnDanger {
  height: 32px;
  padding: 0 12px;
  background: transparent;
  color: var(--color-danger);
  border: 1px solid var(--color-danger);
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
}

.btnDanger:hover { background: var(--color-danger-bg); }
.btnDanger:disabled { opacity: 0.45; cursor: not-allowed; }

.btnSecondary {
  height: 36px;
  padding: 0 14px;
  background: var(--color-surface);
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}

.btnSecondary:hover { background: var(--color-surface-2); }

/* Badges kind */
.kindStaging { background: var(--color-warning-bg); color: var(--color-warning); font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: var(--radius-sm); }
.kindPreview { background: var(--color-info-bg, #cffafe); color: var(--color-info, #0891b2); font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: var(--radius-sm); }
.kindDev { background: var(--color-success-bg); color: var(--color-success); font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: var(--radius-sm); }
.kindInternal { background: var(--color-surface-2); color: var(--color-text-muted); font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: var(--radius-sm); }

.roleBadge { background: var(--color-primary-s); color: var(--color-primary); font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: var(--radius-sm); }
.roleAdmin { background: #ede9fe; color: #7c3aed; font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: var(--radius-sm); }
.roleRevoked { background: var(--color-danger-bg); color: var(--color-danger); font-size: 11px; padding: 2px 7px; border-radius: var(--radius-sm); }

.emptyRow td { text-align: center; color: var(--color-text-muted); padding: 28px; font-size: 13px; }

.errorMsg { color: var(--color-danger); font-size: 12px; margin-top: 6px; }
```

- [ ] **Step 2 : Mettre à jour `apps/web/src/app/(admin)/admin/page.tsx`**

```typescript
// Back-office — Dashboard
// Référence visuelle : docs/ds/mockups/devgate-backoffice.mockup.html
import { redirect } from "next/navigation";
import { serverAdminApi, AdminApiError } from "@/lib/api/server-admin";
import styles from "./admin.module.css";

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("fr-FR", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

export default async function AdminDashboardPage() {
  let stats;
  let events;

  try {
    [stats, events] = await Promise.all([
      serverAdminApi.stats(),
      serverAdminApi.auditEvents(10),
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

  return (
    <div className={styles.page}>
      <h1 className={styles.pageTitle}>Dashboard</h1>
      <p className={styles.pageSub}>Vue d'ensemble de l'activité DevGate</p>

      <div className={styles.statsGrid}>
        {STATS.map((s) => (
          <div key={s.label} className={styles.statCard}>
            <div className={styles.statLabel}>{s.label}</div>
            <div className={styles.statValue}>{s.value}</div>
          </div>
        ))}
      </div>

      <div className={styles.sectionTitle}>Activité récente</div>
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
                <td><span className={styles.eventType}>{e.event_type}</span></td>
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

- [ ] **Step 3 : Vérifier la compilation TypeScript**

```bash
cd /Users/amiellavon/Sites/Captive-serveur/apps/web
npx tsc --noEmit 2>&1 | head -20
```

Expected: aucune erreur.

- [ ] **Step 4 : Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/web/src/app/\(admin\)/admin/page.tsx apps/web/src/app/\(admin\)/admin/admin.module.css
git commit -m "feat(admin): dashboard page avec stats et activité récente"
```

---

## Task 6: Frontend — Clients page (liste orgs + créer org + créer projet)

**Files:**
- Modify: `apps/web/src/app/(admin)/admin/clients/page.tsx`
- Create: `apps/web/src/app/(admin)/admin/clients/ClientsClient.tsx`
- Create: `apps/web/src/app/(admin)/admin/clients/clients.module.css`

- [ ] **Step 1 : Créer `apps/web/src/app/(admin)/admin/clients/clients.module.css`**

Importer le module parent pour réutiliser les styles communs, et ajouter les spécificités :

```css
/* Réutiliser admin.module.css pour table/btn — CSS module local pour overrides */

.page {
  padding: 32px 36px;
  max-width: 1100px;
}

.pageTitle {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.3px;
  margin-bottom: 2px;
}

.pageSub {
  font-size: 13px;
  color: var(--color-text-muted);
  margin-bottom: 24px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.sectionTitle {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
}

.table {
  width: 100%;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  border-collapse: collapse;
  overflow: hidden;
}

.table th {
  text-align: left;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.4px;
  padding: 10px 16px;
  background: var(--color-surface-2);
  border-bottom: 1px solid var(--color-border);
}

.table td {
  padding: 11px 16px;
  font-size: 13px;
  border-bottom: 1px solid var(--color-border);
  vertical-align: middle;
}

.table tr:last-child td { border-bottom: none; }

.orgName { font-weight: 600; }
.orgSlug { font-size: 12px; color: var(--color-text-muted); }

.count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 20px;
  background: var(--color-surface-2);
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-muted);
  padding: 0 6px;
}

.emptyRow td { text-align: center; color: var(--color-text-muted); padding: 28px; font-size: 13px; }

/* Drawer / modal */
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.35);
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
}

.drawer {
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  padding: 28px;
  width: 420px;
  box-shadow: var(--shadow-md);
}

.drawerTitle {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 18px;
}

.formGroup {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 14px;
}

.label {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-muted);
}

.input {
  height: 36px;
  padding: 0 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  background: var(--color-surface);
  color: var(--color-text);
}

.input:focus { outline: none; border-color: var(--color-primary); }

.select {
  height: 36px;
  padding: 0 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  background: var(--color-surface);
  color: var(--color-text);
  width: 100%;
}

.drawerActions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 20px;
}

.btnPrimary {
  height: 36px;
  padding: 0 16px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}

.btnPrimary:hover { background: var(--color-primary-h); }
.btnPrimary:disabled { opacity: 0.55; cursor: not-allowed; }

.btnSecondary {
  height: 36px;
  padding: 0 14px;
  background: var(--color-surface);
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}

.btnSecondary:hover { background: var(--color-surface-2); }

.btnLink {
  background: none;
  border: none;
  color: var(--color-primary);
  font-size: 12px;
  cursor: pointer;
  padding: 0;
}

.btnLink:hover { text-decoration: underline; }

.errorMsg { color: var(--color-danger); font-size: 12px; margin-top: 6px; }
```

- [ ] **Step 2 : Créer `apps/web/src/app/(admin)/admin/clients/ClientsClient.tsx`**

```typescript
"use client";

import { useState } from "react";
import { adminApi } from "@/lib/api/client";
import type { OrgItem, ProjectItem } from "@/lib/api/server-admin";
import styles from "./clients.module.css";

interface Props {
  initialOrgs: OrgItem[];
  initialProjects: ProjectItem[];
}

type Modal = null | "create-org" | "create-project";

export function ClientsClient({ initialOrgs, initialProjects }: Props) {
  const [orgs, setOrgs] = useState(initialOrgs);
  const [projects, setProjects] = useState(initialProjects);
  const [modal, setModal] = useState<Modal>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Formulaire org
  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");
  const [orgEmail, setOrgEmail] = useState("");

  // Formulaire projet
  const [projOrgId, setProjOrgId] = useState("");
  const [projName, setProjName] = useState("");
  const [projSlug, setProjSlug] = useState("");

  function openModal(m: Modal) {
    setError(null);
    setModal(m);
  }

  function closeModal() {
    setModal(null);
    setError(null);
    setOrgName(""); setOrgSlug(""); setOrgEmail("");
    setProjOrgId(""); setProjName(""); setProjSlug("");
  }

  async function handleCreateOrg(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await adminApi.organizations.create({
        name: orgName,
        slug: orgSlug,
        support_email: orgEmail || undefined,
      });
      // Recharger la liste via une nouvelle requête client
      const updated = await adminApi.organizations.list() as OrgItem[];
      setOrgs(updated);
      closeModal();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inattendue");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateProject(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await adminApi.projects.create({
        organization_id: projOrgId,
        name: projName,
        slug: projSlug,
      });
      const updated = await adminApi.projects.list() as ProjectItem[];
      setProjects(updated);
      closeModal();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inattendue");
    } finally {
      setLoading(false);
    }
  }

  // Nombre de projets par org
  const projCountByOrg = projects.reduce<Record<string, number>>((acc, p) => {
    acc[p.organization_id] = (acc[p.organization_id] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className={styles.page}>
      <h1 className={styles.pageTitle}>Clients</h1>
      <p className={styles.pageSub}>Organisations rattachées à DevGate</p>

      <div className={styles.toolbar}>
        <span className={styles.sectionTitle}>{orgs.length} client{orgs.length !== 1 ? "s" : ""}</span>
        <div style={{ display: "flex", gap: "8px" }}>
          <button className={styles.btnSecondary} onClick={() => openModal("create-project")}>
            + Nouveau projet
          </button>
          <button className={styles.btnPrimary} onClick={() => openModal("create-org")}>
            + Nouveau client
          </button>
        </div>
      </div>

      <table className={styles.table}>
        <thead>
          <tr>
            <th>Client</th>
            <th>Slug</th>
            <th>Projets</th>
            <th>Environnements</th>
            <th>Utilisateurs actifs</th>
          </tr>
        </thead>
        <tbody>
          {orgs.length === 0 ? (
            <tr className={styles.emptyRow}>
              <td colSpan={5}>Aucun client — créez le premier</td>
            </tr>
          ) : (
            orgs.map((org) => (
              <tr key={org.id}>
                <td>
                  <div className={styles.orgName}>{org.name}</div>
                  {org.support_email && (
                    <div className={styles.orgSlug}>{org.support_email}</div>
                  )}
                </td>
                <td><span className={styles.orgSlug}>{org.slug}</span></td>
                <td><span className={styles.count}>{projCountByOrg[org.id] ?? 0}</span></td>
                <td><span className={styles.count}>{org.env_count}</span></td>
                <td><span className={styles.count}>{org.user_count}</span></td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {/* Modal créer org */}
      {modal === "create-org" && (
        <div className={styles.overlay} onClick={closeModal}>
          <div className={styles.drawer} onClick={(e) => e.stopPropagation()}>
            <div className={styles.drawerTitle}>Nouveau client</div>
            <form onSubmit={handleCreateOrg}>
              <div className={styles.formGroup}>
                <label className={styles.label}>Nom du client *</label>
                <input className={styles.input} value={orgName} onChange={e => setOrgName(e.target.value)} required placeholder="Ex: Acme Corp" />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Slug (identifiant URL) *</label>
                <input className={styles.input} value={orgSlug} onChange={e => setOrgSlug(e.target.value)} required placeholder="acme-corp" pattern="[a-z0-9\-]+" title="Minuscules, chiffres et tirets uniquement" />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Email support</label>
                <input className={styles.input} type="email" value={orgEmail} onChange={e => setOrgEmail(e.target.value)} placeholder="support@acme.com" />
              </div>
              {error && <p className={styles.errorMsg}>{error}</p>}
              <div className={styles.drawerActions}>
                <button type="button" className={styles.btnSecondary} onClick={closeModal}>Annuler</button>
                <button type="submit" className={styles.btnPrimary} disabled={loading}>{loading ? "Création…" : "Créer le client"}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal créer projet */}
      {modal === "create-project" && (
        <div className={styles.overlay} onClick={closeModal}>
          <div className={styles.drawer} onClick={(e) => e.stopPropagation()}>
            <div className={styles.drawerTitle}>Nouveau projet</div>
            <form onSubmit={handleCreateProject}>
              <div className={styles.formGroup}>
                <label className={styles.label}>Client *</label>
                <select className={styles.select} value={projOrgId} onChange={e => setProjOrgId(e.target.value)} required>
                  <option value="">Choisir un client…</option>
                  {orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                </select>
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Nom du projet *</label>
                <input className={styles.input} value={projName} onChange={e => setProjName(e.target.value)} required placeholder="Ex: Refonte site" />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Slug *</label>
                <input className={styles.input} value={projSlug} onChange={e => setProjSlug(e.target.value)} required placeholder="refonte-site" pattern="[a-z0-9\-]+" />
              </div>
              {error && <p className={styles.errorMsg}>{error}</p>}
              <div className={styles.drawerActions}>
                <button type="button" className={styles.btnSecondary} onClick={closeModal}>Annuler</button>
                <button type="submit" className={styles.btnPrimary} disabled={loading}>{loading ? "Création…" : "Créer le projet"}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3 : Mettre à jour `apps/web/src/app/(admin)/admin/clients/page.tsx`**

```typescript
// Back-office — Clients (organisations)
// Référence visuelle : docs/ds/mockups/devgate-backoffice.mockup.html
import { redirect } from "next/navigation";
import { serverAdminApi, AdminApiError } from "@/lib/api/server-admin";
import { ClientsClient } from "./ClientsClient";

export default async function AdminClientsPage() {
  let orgs;
  let projects;

  try {
    [orgs, projects] = await Promise.all([
      serverAdminApi.organizations(),
      serverAdminApi.projects(),
    ]);
  } catch (err) {
    if (err instanceof AdminApiError && err.status === 401) redirect("/login");
    if (err instanceof AdminApiError && err.status === 403) redirect("/access-denied");
    redirect("/session-expired");
  }

  return <ClientsClient initialOrgs={orgs} initialProjects={projects} />;
}
```

- [ ] **Step 4 : Vérifier la compilation TypeScript**

```bash
cd /Users/amiellavon/Sites/Captive-serveur/apps/web
npx tsc --noEmit 2>&1 | head -20
```

Expected: aucune erreur.

- [ ] **Step 5 : Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/web/src/app/\(admin\)/admin/clients/
git commit -m "feat(admin): page Clients avec liste orgs + création org/projet"
```

---

## Task 7: Frontend — Environnements page

**Files:**
- Modify: `apps/web/src/app/(admin)/admin/environments/page.tsx`
- Create: `apps/web/src/app/(admin)/admin/environments/EnvironmentsClient.tsx`
- Create: `apps/web/src/app/(admin)/admin/environments/environments.module.css`

- [ ] **Step 1 : Créer `apps/web/src/app/(admin)/admin/environments/environments.module.css`**

```css
.page { padding: 32px 36px; max-width: 1100px; }
.pageTitle { font-size: 20px; font-weight: 700; letter-spacing: -0.3px; margin-bottom: 2px; }
.pageSub { font-size: 13px; color: var(--color-text-muted); margin-bottom: 24px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.sectionTitle { font-size: 15px; font-weight: 600; color: var(--color-text); }

.table { width: 100%; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); border-collapse: collapse; overflow: hidden; }
.table th { text-align: left; font-size: 11px; font-weight: 600; color: var(--color-text-muted); text-transform: uppercase; letter-spacing: 0.4px; padding: 10px 16px; background: var(--color-surface-2); border-bottom: 1px solid var(--color-border); }
.table td { padding: 11px 16px; font-size: 13px; border-bottom: 1px solid var(--color-border); vertical-align: middle; }
.table tr:last-child td { border-bottom: none; }

.envName { font-weight: 600; }
.envHost { font-size: 12px; color: var(--color-text-muted); }
.orgProject { font-size: 12px; color: var(--color-text-muted); }

.kindBadge { font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: var(--radius-sm); }
.kindStaging { background: var(--color-warning-bg); color: var(--color-warning); }
.kindPreview { background: #cffafe; color: #0891b2; }
.kindDev { background: var(--color-success-bg); color: var(--color-success); }
.kindInternal { background: var(--color-surface-2); color: var(--color-text-muted); }

.statusOnline { background: var(--color-success-bg); color: var(--color-success); font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: var(--radius-sm); }
.statusInactive { background: var(--color-surface-2); color: var(--color-text-muted); font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: var(--radius-sm); }

.authBadge { background: var(--color-primary-s); color: var(--color-primary); font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: var(--radius-sm); }

.emptyRow td { text-align: center; color: var(--color-text-muted); padding: 28px; font-size: 13px; }

.overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.35); z-index: 100; display: flex; align-items: center; justify-content: center; }
.drawer { background: var(--color-surface); border-radius: var(--radius-lg); padding: 28px; width: 480px; box-shadow: var(--shadow-md); max-height: 90vh; overflow-y: auto; }
.drawerTitle { font-size: 16px; font-weight: 700; margin-bottom: 18px; }

.formGroup { display: flex; flex-direction: column; gap: 5px; margin-bottom: 14px; }
.label { font-size: 12px; font-weight: 500; color: var(--color-text-muted); }
.input { height: 36px; padding: 0 10px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); font-size: 13px; background: var(--color-surface); color: var(--color-text); }
.input:focus { outline: none; border-color: var(--color-primary); }
.select { height: 36px; padding: 0 10px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); font-size: 13px; background: var(--color-surface); color: var(--color-text); width: 100%; }
.checkRow { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
.checkLabel { font-size: 13px; color: var(--color-text); }

.drawerActions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }
.btnPrimary { height: 36px; padding: 0 16px; background: var(--color-primary); color: #fff; border: none; border-radius: var(--radius-sm); font-size: 13px; font-weight: 500; cursor: pointer; }
.btnPrimary:hover { background: var(--color-primary-h); }
.btnPrimary:disabled { opacity: 0.55; cursor: not-allowed; }
.btnSecondary { height: 36px; padding: 0 14px; background: var(--color-surface); color: var(--color-text); border: 1px solid var(--color-border); border-radius: var(--radius-sm); font-size: 13px; font-weight: 500; cursor: pointer; }
.btnSecondary:hover { background: var(--color-surface-2); }
.errorMsg { color: var(--color-danger); font-size: 12px; margin-top: 6px; }
```

- [ ] **Step 2 : Créer `apps/web/src/app/(admin)/admin/environments/EnvironmentsClient.tsx`**

```typescript
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
  staging: "Staging", preview: "Preview", dev: "Dev", internal: "Internal",
};

function KindBadge({ kind }: { kind: string }) {
  const cls = styles[`kind${kind.charAt(0).toUpperCase() + kind.slice(1)}`] ?? styles.kindInternal;
  return <span className={`${styles.kindBadge} ${cls}`}>{KIND_LABELS[kind] ?? kind}</span>;
}

export function EnvironmentsClient({ initialEnvs, orgs, initialProjects }: Props) {
  const [envs, setEnvs] = useState(initialEnvs);
  const [projects, setProjects] = useState(initialProjects);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedOrgId, setSelectedOrgId] = useState("");
  const [projId, setProjId] = useState("");
  const [envName, setEnvName] = useState("");
  const [envSlug, setEnvSlug] = useState("");
  const [envKind, setEnvKind] = useState("staging");
  const [hostname, setHostname] = useState("");
  const [requiresAuth, setRequiresAuth] = useState(false);

  const filteredProjects = projects.filter(p => p.organization_id === selectedOrgId);

  function openDrawer() { setError(null); setOpen(true); }
  function closeDrawer() {
    setOpen(false); setError(null);
    setSelectedOrgId(""); setProjId(""); setEnvName(""); setEnvSlug("");
    setEnvKind("staging"); setHostname(""); setRequiresAuth(false);
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
        <span className={styles.sectionTitle}>{envs.length} environnement{envs.length !== 1 ? "s" : ""}</span>
        <button className={styles.btnPrimary} onClick={openDrawer}>+ Nouvel environnement</button>
      </div>

      <table className={styles.table}>
        <thead>
          <tr>
            <th>Environnement</th>
            <th>Client / Projet</th>
            <th>Type</th>
            <th>Statut</th>
            <th>Auth app</th>
          </tr>
        </thead>
        <tbody>
          {envs.length === 0 ? (
            <tr className={styles.emptyRow}><td colSpan={5}>Aucun environnement</td></tr>
          ) : (
            envs.map((e) => (
              <tr key={e.id}>
                <td>
                  <div className={styles.envName}>{e.name}</div>
                  <div className={styles.envHost}>{e.public_hostname}</div>
                </td>
                <td><span className={styles.orgProject}>{e.org_name} / {e.project_name}</span></td>
                <td><KindBadge kind={e.kind} /></td>
                <td>
                  <span className={e.status === "active" ? styles.statusOnline : styles.statusInactive}>
                    {e.status === "active" ? "Actif" : e.status}
                  </span>
                </td>
                <td>
                  {e.requires_app_auth && <span className={styles.authBadge}>Auth requise</span>}
                </td>
              </tr>
            ))
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
                <select className={styles.select} value={selectedOrgId}
                  onChange={e => { setSelectedOrgId(e.target.value); setProjId(""); }} required>
                  <option value="">Choisir un client…</option>
                  {orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                </select>
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Projet *</label>
                <select className={styles.select} value={projId} onChange={e => setProjId(e.target.value)} required disabled={!selectedOrgId}>
                  <option value="">Choisir un projet…</option>
                  {filteredProjects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Nom *</label>
                <input className={styles.input} value={envName} onChange={e => setEnvName(e.target.value)} required placeholder="Staging principal" />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Slug *</label>
                <input className={styles.input} value={envSlug} onChange={e => setEnvSlug(e.target.value)} required placeholder="staging" pattern="[a-z0-9\-]+" />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Type *</label>
                <select className={styles.select} value={envKind} onChange={e => setEnvKind(e.target.value)}>
                  <option value="staging">Staging</option>
                  <option value="preview">Preview</option>
                  <option value="dev">Dev</option>
                  <option value="internal">Internal</option>
                </select>
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Hostname public *</label>
                <input className={styles.input} value={hostname} onChange={e => setHostname(e.target.value)} required placeholder="app.client.example.com" />
              </div>
              <div className={styles.checkRow}>
                <input id="requires-auth" type="checkbox" checked={requiresAuth} onChange={e => setRequiresAuth(e.target.checked)} />
                <label htmlFor="requires-auth" className={styles.checkLabel}>Auth applicative requise</label>
              </div>
              {error && <p className={styles.errorMsg}>{error}</p>}
              <div className={styles.drawerActions}>
                <button type="button" className={styles.btnSecondary} onClick={closeDrawer}>Annuler</button>
                <button type="submit" className={styles.btnPrimary} disabled={loading}>{loading ? "Création…" : "Créer"}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3 : Mettre à jour `apps/web/src/app/(admin)/admin/environments/page.tsx`**

```typescript
// Back-office — Environnements
import { redirect } from "next/navigation";
import { serverAdminApi, AdminApiError } from "@/lib/api/server-admin";
import { EnvironmentsClient } from "./EnvironmentsClient";

export default async function AdminEnvironmentsPage() {
  let envs;
  let orgs;
  let projects;

  try {
    [envs, orgs, projects] = await Promise.all([
      serverAdminApi.environments(),
      serverAdminApi.organizations(),
      serverAdminApi.projects(),
    ]);
  } catch (err) {
    if (err instanceof AdminApiError && err.status === 401) redirect("/login");
    if (err instanceof AdminApiError && err.status === 403) redirect("/access-denied");
    redirect("/session-expired");
  }

  return <EnvironmentsClient initialEnvs={envs} orgs={orgs} initialProjects={projects} />;
}
```

- [ ] **Step 4 : Vérifier la compilation TypeScript**

```bash
cd /Users/amiellavon/Sites/Captive-serveur/apps/web
npx tsc --noEmit 2>&1 | head -20
```

Expected: aucune erreur.

- [ ] **Step 5 : Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/web/src/app/\(admin\)/admin/environments/
git commit -m "feat(admin): page Environnements avec liste + formulaire création"
```

---

## Task 8: Frontend — Accès page (grants)

**Files:**
- Modify: `apps/web/src/app/(admin)/admin/access/page.tsx`
- Create: `apps/web/src/app/(admin)/admin/access/AccessClient.tsx`
- Create: `apps/web/src/app/(admin)/admin/access/access.module.css`

- [ ] **Step 1 : Créer `apps/web/src/app/(admin)/admin/access/access.module.css`**

```css
.page { padding: 32px 36px; max-width: 1100px; }
.pageTitle { font-size: 20px; font-weight: 700; letter-spacing: -0.3px; margin-bottom: 2px; }
.pageSub { font-size: 13px; color: var(--color-text-muted); margin-bottom: 24px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.sectionTitle { font-size: 15px; font-weight: 600; color: var(--color-text); }

.table { width: 100%; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); border-collapse: collapse; overflow: hidden; }
.table th { text-align: left; font-size: 11px; font-weight: 600; color: var(--color-text-muted); text-transform: uppercase; letter-spacing: 0.4px; padding: 10px 16px; background: var(--color-surface-2); border-bottom: 1px solid var(--color-border); }
.table td { padding: 11px 16px; font-size: 13px; border-bottom: 1px solid var(--color-border); vertical-align: middle; }
.table tr:last-child td { border-bottom: none; }

.userEmail { font-weight: 500; }
.dateText { font-size: 12px; color: var(--color-text-muted); }
.emptyRow td { text-align: center; color: var(--color-text-muted); padding: 28px; font-size: 13px; }

.roleMember { background: var(--color-primary-s); color: var(--color-primary); font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: var(--radius-sm); }
.roleAdmin { background: #ede9fe; color: #7c3aed; font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: var(--radius-sm); }
.roleRevoked { background: var(--color-danger-bg); color: var(--color-danger); font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: var(--radius-sm); }

.btnRevoke { height: 30px; padding: 0 12px; background: transparent; color: var(--color-danger); border: 1px solid var(--color-danger); border-radius: var(--radius-sm); font-size: 12px; font-weight: 500; cursor: pointer; }
.btnRevoke:hover { background: var(--color-danger-bg); }
.btnRevoke:disabled { opacity: 0.45; cursor: not-allowed; }

.overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.35); z-index: 100; display: flex; align-items: center; justify-content: center; }
.drawer { background: var(--color-surface); border-radius: var(--radius-lg); padding: 28px; width: 420px; box-shadow: var(--shadow-md); }
.drawerTitle { font-size: 16px; font-weight: 700; margin-bottom: 18px; }

.formGroup { display: flex; flex-direction: column; gap: 5px; margin-bottom: 14px; }
.label { font-size: 12px; font-weight: 500; color: var(--color-text-muted); }
.input { height: 36px; padding: 0 10px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); font-size: 13px; background: var(--color-surface); color: var(--color-text); }
.input:focus { outline: none; border-color: var(--color-primary); }
.select { height: 36px; padding: 0 10px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); font-size: 13px; background: var(--color-surface); color: var(--color-text); width: 100%; }

.drawerActions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }
.btnPrimary { height: 36px; padding: 0 16px; background: var(--color-primary); color: #fff; border: none; border-radius: var(--radius-sm); font-size: 13px; font-weight: 500; cursor: pointer; }
.btnPrimary:hover { background: var(--color-primary-h); }
.btnPrimary:disabled { opacity: 0.55; cursor: not-allowed; }
.btnSecondary { height: 36px; padding: 0 14px; background: var(--color-surface); color: var(--color-text); border: 1px solid var(--color-border); border-radius: var(--radius-sm); font-size: 13px; font-weight: 500; cursor: pointer; }
.btnSecondary:hover { background: var(--color-surface-2); }
.errorMsg { color: var(--color-danger); font-size: 12px; margin-top: 6px; }
```

- [ ] **Step 2 : Créer `apps/web/src/app/(admin)/admin/access/AccessClient.tsx`**

```typescript
"use client";

import { useState } from "react";
import { adminApi } from "@/lib/api/client";
import type { GrantItem, OrgItem } from "@/lib/api/server-admin";
import styles from "./access.module.css";

interface Props {
  initialGrants: GrantItem[];
  orgs: OrgItem[];
}

function RoleBadge({ role, revoked }: { role: string; revoked: boolean }) {
  if (revoked) return <span className={styles.roleRevoked}>Révoqué</span>;
  if (role === "agency_admin") return <span className={styles.roleAdmin}>Admin agence</span>;
  return <span className={styles.roleMember}>{role === "client_member" ? "Membre client" : role}</span>;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" });
}

export function AccessClient({ initialGrants, orgs }: Props) {
  const [grants, setGrants] = useState(initialGrants);
  const [open, setOpen] = useState(false);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [email, setEmail] = useState("");
  const [orgId, setOrgId] = useState("");
  const [role, setRole] = useState("client_member");
  const [displayName, setDisplayName] = useState("");

  function openDrawer() { setError(null); setOpen(true); }
  function closeDrawer() {
    setOpen(false); setError(null);
    setEmail(""); setOrgId(""); setRole("client_member"); setDisplayName("");
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await adminApi.grants.create({ email, organization_id: orgId, role, display_name: displayName || undefined });
      const updated = await adminApi.grants.list() as GrantItem[];
      setGrants(updated);
      closeDrawer();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inattendue");
    } finally {
      setLoading(false);
    }
  }

  async function handleRevoke(grantId: string) {
    setRevokingId(grantId);
    try {
      await adminApi.grants.revoke(grantId);
      setGrants(prev => prev.map(g => g.id === grantId ? { ...g, revoked_at: new Date().toISOString() } : g));
    } finally {
      setRevokingId(null);
    }
  }

  const active = grants.filter(g => !g.revoked_at);
  const revoked = grants.filter(g => !!g.revoked_at);

  return (
    <div className={styles.page}>
      <h1 className={styles.pageTitle}>Accès</h1>
      <p className={styles.pageSub}>Gestion des accès utilisateurs par organisation</p>

      <div className={styles.toolbar}>
        <span className={styles.sectionTitle}>{active.length} accès actif{active.length !== 1 ? "s" : ""}</span>
        <button className={styles.btnPrimary} onClick={openDrawer}>+ Inviter un utilisateur</button>
      </div>

      <table className={styles.table}>
        <thead>
          <tr>
            <th>Utilisateur</th>
            <th>Organisation</th>
            <th>Rôle</th>
            <th>Accordé le</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {grants.length === 0 ? (
            <tr className={styles.emptyRow}><td colSpan={5}>Aucun accès configuré</td></tr>
          ) : (
            [...active, ...revoked].map((g) => (
              <tr key={g.id}>
                <td><span className={styles.userEmail}>{g.user_email}</span></td>
                <td>{g.org_name}</td>
                <td><RoleBadge role={g.role} revoked={!!g.revoked_at} /></td>
                <td><span className={styles.dateText}>{formatDate(g.created_at)}</span></td>
                <td>
                  <button
                    className={styles.btnRevoke}
                    disabled={!!g.revoked_at || revokingId === g.id}
                    onClick={() => handleRevoke(g.id)}
                  >
                    {revokingId === g.id ? "…" : "Révoquer"}
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {open && (
        <div className={styles.overlay} onClick={closeDrawer}>
          <div className={styles.drawer} onClick={(e) => e.stopPropagation()}>
            <div className={styles.drawerTitle}>Inviter un utilisateur</div>
            <form onSubmit={handleCreate}>
              <div className={styles.formGroup}>
                <label className={styles.label}>Email *</label>
                <input className={styles.input} type="email" value={email} onChange={e => setEmail(e.target.value)} required placeholder="user@client.com" />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Nom affiché</label>
                <input className={styles.input} value={displayName} onChange={e => setDisplayName(e.target.value)} placeholder="Jean Dupont" />
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Organisation *</label>
                <select className={styles.select} value={orgId} onChange={e => setOrgId(e.target.value)} required>
                  <option value="">Choisir une organisation…</option>
                  {orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                </select>
              </div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Rôle *</label>
                <select className={styles.select} value={role} onChange={e => setRole(e.target.value)}>
                  <option value="client_member">Membre client</option>
                  <option value="reviewer">Reviewer</option>
                  <option value="agency_admin">Admin agence</option>
                </select>
              </div>
              {error && <p className={styles.errorMsg}>{error}</p>}
              <div className={styles.drawerActions}>
                <button type="button" className={styles.btnSecondary} onClick={closeDrawer}>Annuler</button>
                <button type="submit" className={styles.btnPrimary} disabled={loading}>{loading ? "Invitation…" : "Inviter"}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3 : Mettre à jour `apps/web/src/app/(admin)/admin/access/page.tsx`**

```typescript
// Back-office — Accès (grants)
import { redirect } from "next/navigation";
import { serverAdminApi, AdminApiError } from "@/lib/api/server-admin";
import { AccessClient } from "./AccessClient";

export default async function AdminAccessPage() {
  let grants;
  let orgs;

  try {
    [grants, orgs] = await Promise.all([
      serverAdminApi.grants(),
      serverAdminApi.organizations(),
    ]);
  } catch (err) {
    if (err instanceof AdminApiError && err.status === 401) redirect("/login");
    if (err instanceof AdminApiError && err.status === 403) redirect("/access-denied");
    redirect("/session-expired");
  }

  return <AccessClient initialGrants={grants} orgs={orgs} />;
}
```

- [ ] **Step 4 : Vérifier la compilation TypeScript**

```bash
cd /Users/amiellavon/Sites/Captive-serveur/apps/web
npx tsc --noEmit 2>&1 | head -20
```

Expected: aucune erreur.

- [ ] **Step 5 : Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/web/src/app/\(admin\)/admin/access/
git commit -m "feat(admin): page Accès avec liste grants + invitation + révocation"
```

---

## Task 9: Frontend — Audit page

**Files:**
- Modify: `apps/web/src/app/(admin)/admin/audit/page.tsx`
- Create: `apps/web/src/app/(admin)/admin/audit/AuditClient.tsx`
- Create: `apps/web/src/app/(admin)/admin/audit/audit.module.css`

- [ ] **Step 1 : Créer `apps/web/src/app/(admin)/admin/audit/audit.module.css`**

```css
.page { padding: 32px 36px; max-width: 1100px; }
.pageTitle { font-size: 20px; font-weight: 700; letter-spacing: -0.3px; margin-bottom: 2px; }
.pageSub { font-size: 13px; color: var(--color-text-muted); margin-bottom: 24px; }

.toolbar { display: flex; gap: 10px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
.filterLabel { font-size: 12px; color: var(--color-text-muted); font-weight: 500; }
.select { height: 34px; padding: 0 10px; border: 1px solid var(--color-border); border-radius: var(--radius-sm); font-size: 13px; background: var(--color-surface); color: var(--color-text); }

.table { width: 100%; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); border-collapse: collapse; overflow: hidden; }
.table th { text-align: left; font-size: 11px; font-weight: 600; color: var(--color-text-muted); text-transform: uppercase; letter-spacing: 0.4px; padding: 10px 16px; background: var(--color-surface-2); border-bottom: 1px solid var(--color-border); }
.table td { padding: 10px 16px; font-size: 13px; border-bottom: 1px solid var(--color-border); vertical-align: middle; }
.table tr:last-child td { border-bottom: none; }

.dateText { font-size: 12px; color: var(--color-text-muted); white-space: nowrap; }
.eventType { font-size: 11px; font-weight: 600; font-family: monospace; padding: 2px 7px; border-radius: var(--radius-sm); background: var(--color-surface-2); color: var(--color-text-muted); }
.actorText { font-size: 12px; color: var(--color-text-muted); }

/* Catégorie couleur */
.catAuth .eventType { background: var(--color-warning-bg); color: var(--color-warning); }
.catAdmin .eventType { background: var(--color-primary-s); color: var(--color-primary); }
.catGateway .eventType { background: var(--color-success-bg); color: var(--color-success); }

.emptyRow td { text-align: center; color: var(--color-text-muted); padding: 32px; font-size: 13px; }
.countNote { font-size: 12px; color: var(--color-text-muted); margin-top: 10px; }
```

- [ ] **Step 2 : Créer `apps/web/src/app/(admin)/admin/audit/AuditClient.tsx`**

```typescript
"use client";

import { useState, useMemo } from "react";
import type { AdminAuditEvent } from "@/lib/api/server-admin";
import styles from "./audit.module.css";

interface Props {
  initialEvents: AdminAuditEvent[];
}

const FILTERS = [
  { label: "Tous", value: "" },
  { label: "Auth", value: "auth" },
  { label: "Admin", value: "admin" },
  { label: "Gateway", value: "gateway" },
];

function rowClass(eventType: string): string {
  if (eventType.startsWith("auth.")) return styles.catAuth;
  if (eventType.startsWith("admin.")) return styles.catAdmin;
  if (eventType.startsWith("gateway.")) return styles.catGateway;
  return "";
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("fr-FR", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

export function AuditClient({ initialEvents }: Props) {
  const [filter, setFilter] = useState("");

  const filtered = useMemo(() => {
    if (!filter) return initialEvents;
    return initialEvents.filter(e => e.event_type.startsWith(filter + "."));
  }, [initialEvents, filter]);

  return (
    <div className={styles.page}>
      <h1 className={styles.pageTitle}>Audit log</h1>
      <p className={styles.pageSub}>Traçabilité des actions sur DevGate</p>

      <div className={styles.toolbar}>
        <span className={styles.filterLabel}>Catégorie :</span>
        {FILTERS.map(f => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            style={{
              padding: "4px 12px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--color-border)",
              background: filter === f.value ? "var(--color-primary)" : "var(--color-surface)",
              color: filter === f.value ? "#fff" : "var(--color-text)",
              fontSize: "12px",
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

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
          {filtered.length === 0 ? (
            <tr className={styles.emptyRow}>
              <td colSpan={4}>Aucun événement{filter ? ` pour la catégorie "${filter}"` : ""}</td>
            </tr>
          ) : (
            filtered.map((e) => (
              <tr key={e.id} className={rowClass(e.event_type)}>
                <td><span className={styles.dateText}>{formatDate(e.created_at)}</span></td>
                <td><span className={styles.eventType}>{e.event_type}</span></td>
                <td><span className={styles.actorText}>{e.actor_user_id ?? "système"}</span></td>
                <td>
                  {e.target_id ? (
                    <span className={styles.actorText}>{e.target_type} · {e.target_id.slice(0, 8)}…</span>
                  ) : "—"}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
      {filtered.length > 0 && (
        <p className={styles.countNote}>{filtered.length} événement{filtered.length !== 1 ? "s" : ""} affiché{filtered.length !== 1 ? "s" : ""}</p>
      )}
    </div>
  );
}
```

- [ ] **Step 3 : Mettre à jour `apps/web/src/app/(admin)/admin/audit/page.tsx`**

```typescript
// Back-office — Audit log
import { redirect } from "next/navigation";
import { serverAdminApi, AdminApiError } from "@/lib/api/server-admin";
import { AuditClient } from "./AuditClient";

export default async function AdminAuditPage() {
  let events;

  try {
    events = await serverAdminApi.auditEvents(100);
  } catch (err) {
    if (err instanceof AdminApiError && err.status === 401) redirect("/login");
    if (err instanceof AdminApiError && err.status === 403) redirect("/access-denied");
    redirect("/session-expired");
  }

  return <AuditClient initialEvents={events} />;
}
```

- [ ] **Step 4 : Vérifier la compilation TypeScript complète**

```bash
cd /Users/amiellavon/Sites/Captive-serveur/apps/web
npx tsc --noEmit 2>&1 | head -20
```

Expected: aucune erreur.

- [ ] **Step 5 : Lancer les tests vitest pour vérifier qu'aucune régression**

```bash
cd /Users/amiellavon/Sites/Captive-serveur/apps/web
npx vitest run 2>&1 | tail -15
```

Expected: tous les tests existants passent.

- [ ] **Step 6 : Lancer tous les tests pytest**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/ -v 2>&1 | tail -20
```

Expected: tous les tests passent.

- [ ] **Step 7 : Commit final**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/web/src/app/\(admin\)/admin/audit/
git commit -m "feat(admin): page Audit avec log filtrable par catégorie"
```

---

## Vérification finale

Après tous les commits, vérifier que le back-office est opérationnel manuellement :

1. Se connecter avec un utilisateur `kind="agency"` (créer via seed si besoin)
2. Naviguer vers `http://localhost:3001/admin`
3. Dashboard doit afficher les stats (0 clients, 0 envs, etc.)
4. Créer un client dans `/admin/clients`
5. Créer un projet pour ce client
6. Créer un environnement dans `/admin/environments`
7. Inviter un utilisateur dans `/admin/access`
8. Vérifier que les événements apparaissent dans `/admin/audit`
9. Se connecter avec l'utilisateur invité → il doit voir la ressource dans le portail

Pour créer un admin rapidement (si pas encore de seed) :

```bash
docker compose exec api python -c "
from app.database import SessionLocal
from app.shared.models import User
db = SessionLocal()
admin = User(email='admin@agency.com', display_name='Admin Agence', kind='agency', status='active')
db.add(admin)
db.commit()
print('Admin créé:', admin.id)
"
```

Puis utiliser le flow magic link depuis `/login` avec `admin@agency.com`.
