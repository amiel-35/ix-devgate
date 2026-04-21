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

# Fixed UUIDs used across test fixtures
_UUID_ADMIN = "00000000-0000-0000-0000-000000000001"
_UUID_ORG_1 = "00000000-0000-0000-0000-000000000010"
_UUID_PROJ_1 = "00000000-0000-0000-0000-000000000020"
_UUID_ENV_1 = "00000000-0000-0000-0000-000000000030"
_UUID_CLIENT = "00000000-0000-0000-0000-000000000040"
_UUID_GRANT_1 = "00000000-0000-0000-0000-000000000050"
_UUID_ORG_TOK2 = "00000000-0000-0000-0000-000000000060"
_UUID_PROJ_TOK2 = "00000000-0000-0000-0000-000000000070"
_UUID_ENV_TOK2 = "00000000-0000-0000-0000-000000000080"
_UUID_NONEXISTENT = "00000000-0000-0000-0000-999999999999"


# ── Helpers ───────────────────────────────────────────────────────

def _make_admin(db_session, session_id="s-admin"):
    admin = User(
        id=_UUID_ADMIN,
        email="admin@agency.com",
        display_name="Admin Agence",
        kind="agency",
        status="active",
    )
    db_session.add(admin)
    # L'admin doit avoir un grant agency_admin actif (H-01)
    org_agency = Organization(id="org-agency", name="Agence", slug="agence")
    db_session.add(org_agency)
    grant = AccessGrant(
        id="grant-admin-1",
        user_id="admin-1",
        organization_id="org-agency",
        role="agency_admin",
    )
    db_session.add(grant)
    session = SessionModel(
        id=session_id,
        user_id=_UUID_ADMIN,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=7),
    )
    db_session.add(session)
    db_session.commit()
    return admin


def _make_org(db_session, org_id=_UUID_ORG_1, name="Client X", slug="client-x"):
    org = Organization(id=org_id, name=name, slug=slug)
    db_session.add(org)
    db_session.commit()
    return org


def _make_project(db_session, proj_id=_UUID_PROJ_1, org_id=_UUID_ORG_1):
    p = Project(id=proj_id, organization_id=org_id, name="Refonte", slug="refonte")
    db_session.add(p)
    db_session.commit()
    return p


def _make_env(db_session, env_id=_UUID_ENV_1, proj_id=_UUID_PROJ_1):
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


def test_agency_user_without_admin_grant_is_forbidden(client, db_session):
    """Un user kind='agency' sans grant agency_admin doit recevoir 403."""
    from app.shared.models import User, Session as DevSession
    import uuid, datetime
    user = User(
        id=str(uuid.uuid4()),
        email="agency-no-grant@example.com",
        kind="agency",
        status="active",
    )
    db_session.add(user)
    session = DevSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=7),
    )
    db_session.add(session)
    db_session.commit()

    response = client.get(
        "/admin/stats",
        cookies={"devgate_session": session.id},
    )
    assert response.status_code == 403, (
        f"Un user agency sans grant doit être refusé, got {response.status_code}"
    )


# ── GET /admin/stats ──────────────────────────────────────────────

def test_stats_empty(client, db_session):
    _make_admin(db_session)
    _auth(client)
    r = client.get("/admin/stats")
    assert r.status_code == 200
    data = r.json()
    # _make_admin crée org-agency pour le grant agency_admin (H-01)
    assert data["active_orgs"] == 1
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
    # org-agency (admin grant) + org-1 (client) = 2
    assert data["active_orgs"] == 2
    assert data["active_envs"] == 1


# ── GET /admin/organizations ──────────────────────────────────────

def test_list_orgs_empty(client, db_session):
    _make_admin(db_session)
    _auth(client)
    r = client.get("/admin/organizations")
    assert r.status_code == 200
    # _make_admin crée org-agency pour le grant agency_admin (H-01)
    orgs = r.json()
    assert len(orgs) == 1
    assert orgs[0]["id"] == "org-agency"


def test_list_orgs_with_counts(client, db_session):
    _make_admin(db_session)
    _auth(client)
    _make_org(db_session)
    _make_project(db_session)
    _make_env(db_session)

    r = client.get("/admin/organizations")
    assert r.status_code == 200
    orgs = r.json()
    # org-agency (admin grant) + org-1 (client) = 2
    assert len(orgs) == 2
    client_org = next(o for o in orgs if o["id"] == "org-1")
    assert client_org["name"] == "Client X"
    assert client_org["env_count"] == 1
    assert client_org["user_count"] == 0


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

    r = client.get(f"/admin/projects?org_id={_UUID_ORG_1}")
    assert r.status_code == 200
    projects = r.json()
    assert len(projects) == 1
    assert projects[0]["name"] == "Refonte"


def test_create_project(client, db_session):
    _make_admin(db_session)
    _auth(client)
    _make_org(db_session)

    r = client.post("/admin/projects", json={
        "organization_id": _UUID_ORG_1,
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
        "project_id": _UUID_PROJ_1,
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

    user = User(id=_UUID_CLIENT, email="client@test.com", kind="client", status="active")
    db_session.add(user)
    grant = AccessGrant(
        id=_UUID_GRANT_1,
        user_id=_UUID_CLIENT,
        organization_id=_UUID_ORG_1,
        role="client_member",
    )
    db_session.add(grant)
    db_session.commit()

    r = client.get("/admin/access-grants")
    assert r.status_code == 200
    grants = r.json()
    # grant-admin-1 (agency_admin) + grant-1 (client_member) = 2
    assert len(grants) == 2
    client_grant = next(g for g in grants if g["id"] == "grant-1")
    assert client_grant["user_email"] == "client@test.com"
    assert client_grant["org_name"] == "Client X"
    assert client_grant["revoked_at"] is None


# ── POST /admin/access-grants ─────────────────────────────────────

def test_create_grant_creates_user_if_missing(client, db_session):
    _make_admin(db_session)
    _auth(client)
    _make_org(db_session)

    r = client.post("/admin/access-grants", json={
        "email": "nouveau@client.com",
        "organization_id": _UUID_ORG_1,
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

    user = User(id=_UUID_CLIENT, email="client@test.com", kind="client", status="active")
    db_session.add(user)
    grant = AccessGrant(id=_UUID_GRANT_1, user_id=_UUID_CLIENT, organization_id=_UUID_ORG_1, role="client_member")
    db_session.add(grant)
    db_session.commit()

    r = client.delete(f"/admin/access-grants/{_UUID_GRANT_1}")
    assert r.status_code == 204

    db_session.refresh(grant)
    assert grant.revoked_at is not None


def test_revoke_grant_idempotent(client, db_session):
    """Révoquer deux fois ne doit pas retourner d'erreur"""
    _make_admin(db_session)
    _auth(client)
    _make_org(db_session)

    user = User(id=_UUID_CLIENT, email="client@test.com", kind="client", status="active")
    db_session.add(user)
    grant = AccessGrant(id=_UUID_GRANT_1, user_id=_UUID_CLIENT, organization_id=_UUID_ORG_1, role="client_member")
    db_session.add(grant)
    db_session.commit()

    client.delete(f"/admin/access-grants/{_UUID_GRANT_1}")
    r = client.delete(f"/admin/access-grants/{_UUID_GRANT_1}")
    assert r.status_code == 204


def test_revoke_grant_not_found(client, db_session):
    _make_admin(db_session)
    _auth(client)
    # Use a valid UUID that doesn't exist in DB → should return 404
    r = client.delete(f"/admin/access-grants/{_UUID_NONEXISTENT}")
    assert r.status_code == 404


# ── GET /admin/audit-events ───────────────────────────────────────

def test_list_audit_events(client, db_session):
    _make_admin(db_session)
    _auth(client)

    evt = AuditEvent(
        id="evt-1",
        event_type="admin.organization.created",
        actor_user_id=_UUID_ADMIN,
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


# ── PUT /admin/environments/{id}/service-token ────────────────────

import base64

_TEST_MASTER_KEY_4 = base64.b64encode(b"a" * 32).decode()


def _make_env_for_token_test(db_session):
    org = Organization(id=_UUID_ORG_TOK2, name="Token Org", slug="tok-org2")
    proj = Project(id=_UUID_PROJ_TOK2, organization_id=_UUID_ORG_TOK2, name="P", slug="p2")
    env = Environment(
        id=_UUID_ENV_TOK2, project_id=_UUID_PROJ_TOK2, name="E", slug="e2",
        kind="staging", public_hostname="e2.example.com",
        upstream_hostname="upstream2.example.com", status="active",
    )
    db_session.add_all([org, proj, env])
    db_session.commit()


def test_store_service_token_sets_ref(client, db_session, monkeypatch):
    """PUT /admin/environments/{id}/service-token stocke le token et met à jour service_token_ref."""
    import app.config as _cfg
    monkeypatch.setattr(_cfg.settings, "DEVGATE_MASTER_KEY", _TEST_MASTER_KEY_4)

    _make_admin(db_session)
    _auth(client)
    _make_env_for_token_test(db_session)

    res = client.put(
        f"/admin/environments/{_UUID_ENV_TOK2}/service-token",
        json={"client_id": "cf-id-123", "client_secret": "cf-secret-456"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["ok"] is True

    db_session.expire_all()
    env = db_session.query(Environment).filter(Environment.id == _UUID_ENV_TOK2).first()
    assert env.service_token_ref is not None
    assert env.service_token_ref.startswith("sec_")


def test_store_service_token_unknown_env_returns_404(client, db_session, monkeypatch):
    import app.config as _cfg
    monkeypatch.setattr(_cfg.settings, "DEVGATE_MASTER_KEY", _TEST_MASTER_KEY_4)
    _make_admin(db_session)
    _auth(client)

    # Use a valid UUID that doesn't exist in DB → should return 404
    res = client.put(
        f"/admin/environments/{_UUID_NONEXISTENT}/service-token",
        json={"client_id": "x", "client_secret": "y"},
    )
    assert res.status_code == 404


# ── GET /admin/environments — health_status ───────────────────────

from datetime import datetime, timezone
from app.shared.models import TunnelHealthSnapshot


def _make_health_snapshot(db_session, env_id=_UUID_ENV_1, status="online", latency_ms=95):
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
    _make_health_snapshot(db_session, env_id=_UUID_ENV_1, status="online", latency_ms=95)

    r = client.get("/admin/environments")
    assert r.status_code == 200
    envs = r.json()
    assert envs[0]["health_status"] == "online"
    assert envs[0]["health_latency_ms"] == 95


# ── GET /admin/gateway-stats ──────────────────────────────────────

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
    assert data["total_requests"] == 5  # 4 accessed + 1 failed
    assert data["errors_5xx"] == 1
    assert data["cf_refused"] == 1
    assert data["upstream_unavailable"] == 1
    # latencies from accessed events: [100, 200, 50, 30] → avg = 95
    assert data["avg_latency_ms"] == 95


# ── UUID validation (F-05) ────────────────────────────────────────

def test_invalid_uuid_env_id_ping_returns_422(client, db_session):
    """Un env_id non-UUID sur /admin/environments/{env_id}/ping doit retourner 422."""
    _make_admin(db_session)
    _auth(client)
    resp = client.post("/admin/environments/not-a-uuid/ping")
    assert resp.status_code == 422


def test_invalid_uuid_env_id_activate_returns_422(client, db_session):
    """Un env_id non-UUID sur /admin/environments/{env_id}/activate doit retourner 422."""
    _make_admin(db_session)
    _auth(client)
    resp = client.post("/admin/environments/not-a-uuid/activate")
    assert resp.status_code == 422


def test_invalid_uuid_grant_id_revoke_returns_422(client, db_session):
    """Un grant_id non-UUID sur /admin/access-grants/{grant_id} doit retourner 422."""
    _make_admin(db_session)
    _auth(client)
    resp = client.delete("/admin/access-grants/not-a-uuid")
    assert resp.status_code == 422
