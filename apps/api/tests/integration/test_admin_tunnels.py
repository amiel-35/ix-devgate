"""Tests d'intégration — endpoints admin tunnels."""
from datetime import datetime, timedelta, timezone

from app.shared.models import (
    AccessGrant, DiscoveredTunnel, Environment, Organization, Project,
    Session as SessionModel, User,
)

# Fixed UUIDs used in tunnel test fixtures
_TUN_ORG = "00000000-0000-0000-0001-000000000010"
_TUN_USER = "00000000-0000-0000-0001-000000000020"
_TUN_GRANT = "00000000-0000-0000-0001-000000000030"
_TUN_PROJ = "00000000-0000-0000-0001-000000000040"
_TUN_ENV = "00000000-0000-0000-0001-000000000050"


def _setup_admin(db_session):
    org = Organization(id=_TUN_ORG, name="Tun Org", slug="tun-org")
    user = User(id=_TUN_USER, email="tun@test.com", kind="agency", status="active")
    grant = AccessGrant(id=_TUN_GRANT, user_id=_TUN_USER, organization_id=_TUN_ORG, role="agency_admin")
    db_session.add_all([org, user, grant])
    db_session.commit()


def _auth(client, db_session):
    sess = SessionModel(
        id="s-tun",
        user_id=_TUN_USER,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=1),
    )
    db_session.add(sess)
    db_session.commit()
    client.cookies.set("devgate_session", "s-tun")


def _make_tunnel(db_session, tunnel_id="t-1", name="devgate-test", status="discovered"):
    dt = DiscoveredTunnel(
        cloudflare_tunnel_id=tunnel_id,
        name=name,
        status=status,
    )
    db_session.add(dt)
    db_session.commit()
    return dt


def _make_env(db_session):
    proj = Project(id=_TUN_PROJ, organization_id=_TUN_ORG, name="P", slug="p")
    env = Environment(
        id=_TUN_ENV, project_id=_TUN_PROJ, name="E", slug="e",
        kind="staging", public_hostname="e.tun.example.com",
        upstream_hostname="e.cfargotunnel.com", status="active",
    )
    db_session.add_all([proj, env])
    db_session.commit()
    return env


def test_list_discovered_tunnels_empty(client, db_session):
    _setup_admin(db_session)
    _auth(client, db_session)
    res = client.get("/admin/discovered-tunnels")
    assert res.status_code == 200
    assert res.json() == []


def test_list_discovered_tunnels_returns_tunnels(client, db_session):
    _setup_admin(db_session)
    _auth(client, db_session)
    _make_tunnel(db_session)
    res = client.get("/admin/discovered-tunnels")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["name"] == "devgate-test"
    assert data[0]["status"] == "discovered"


def test_assign_tunnel_to_environment(client, db_session):
    _setup_admin(db_session)
    _auth(client, db_session)
    tunnel = _make_tunnel(db_session)
    env = _make_env(db_session)

    res = client.post(
        f"/admin/discovered-tunnels/{tunnel.id}/assign",
        json={"environment_id": _TUN_ENV},
    )
    assert res.status_code == 200, res.text
    assert res.json()["ok"] is True

    db_session.expire_all()
    t = db_session.query(DiscoveredTunnel).filter(DiscoveredTunnel.id == tunnel.id).first()
    e = db_session.query(Environment).filter(Environment.id == _TUN_ENV).first()
    assert t.status == "assigned"
    assert e.cloudflare_tunnel_id == "t-1"
    assert e.discovered_tunnel_id == tunnel.id


def test_assign_tunnel_unknown_env_returns_404(client, db_session):
    _setup_admin(db_session)
    _auth(client, db_session)
    tunnel = _make_tunnel(db_session)
    # Use a valid UUID that doesn't exist → should return 404
    res = client.post(
        f"/admin/discovered-tunnels/{tunnel.id}/assign",
        json={"environment_id": "00000000-0000-0000-0001-999999999999"},
    )
    assert res.status_code == 404


import base64


def test_activate_environment_runs_provisioner(client, db_session, monkeypatch):
    """POST /admin/environments/{id}/activate crée un ProvisioningJob et le démarre."""
    TEST_MASTER_KEY = base64.b64encode(b"a" * 32).decode()
    import app.config as _cfg
    monkeypatch.setattr(_cfg.settings, "DEVGATE_MASTER_KEY", TEST_MASTER_KEY)

    # Setup env avec tunnel assigné
    _setup_admin(db_session)
    _auth(client, db_session)
    tunnel = _make_tunnel(db_session, status="assigned")
    env = _make_env(db_session)
    env.cloudflare_tunnel_id = tunnel.cloudflare_tunnel_id
    db_session.commit()

    # Injecter un FakeCFClient pour ne pas appeler la vraie API
    from app.modules.cloudflare.fake_client import FakeCFClient
    fake = FakeCFClient()

    monkeypatch.setattr(
        "app.modules.admin.router._get_cf_client_for_activate",
        lambda: fake,
    )

    res = client.post(f"/admin/environments/{_TUN_ENV}/activate")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["state"] == "active"
    assert data["job_id"] is not None

    from app.shared.models import ProvisioningJob
    job = db_session.query(ProvisioningJob).filter(
        ProvisioningJob.environment_id == _TUN_ENV
    ).first()
    assert job is not None
    assert job.state == "active"
