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
    _make_org(db_session)
    _make_project(db_session)
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
    _make_org(db_session)
    _make_project(db_session)
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
    _make_org(db_session)

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


def test_create_grant_unknown_org(client, db_session):
    _make_admin(db_session)
    _auth(client)

    r = client.post("/admin/access-grants", json={
        "email": "x@test.com",
        "organization_id": "unknown",
        "role": "client_member",
    })
    assert r.status_code == 404


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


def test_revoke_grant_idempotent(client, db_session):
    """Révoquer deux fois ne doit pas retourner d'erreur"""
    _make_admin(db_session)
    _auth(client)
    _make_org(db_session)

    user = User(id="u-client", email="client@test.com", kind="client", status="active")
    db_session.add(user)
    grant = AccessGrant(id="grant-1", user_id="u-client", organization_id="org-1", role="client_member")
    db_session.add(grant)
    db_session.commit()

    client.delete("/admin/access-grants/grant-1")
    r = client.delete("/admin/access-grants/grant-1")
    assert r.status_code == 204


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


def test_list_audit_events_limit_capped(client, db_session):
    _make_admin(db_session)
    _auth(client)
    r = client.get("/admin/audit-events?limit=999")
    # FastAPI retourne 422 si la valeur dépasse le max Query(le=200)
    assert r.status_code == 422
