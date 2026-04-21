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

# Fixed UUIDs used in gateway test fixtures
_GW_USER = "00000000-0000-0000-0002-000000000010"
_GW_ORG = "00000000-0000-0000-0002-000000000020"
_GW_PROJ = "00000000-0000-0000-0002-000000000030"
_GW_ENV = "00000000-0000-0000-0002-000000000040"
_GW_GRANT = "00000000-0000-0000-0002-000000000050"
_GW_ENV_NOGRANT = "00000000-0000-0000-0002-000000000060"
_GW_ORG_NOGRANT = "00000000-0000-0000-0002-000000000070"
_GW_PROJ_NOGRANT = "00000000-0000-0000-0002-000000000080"
_GW_ENV_NONEXISTENT = "00000000-0000-0000-0002-999999999999"


# ── Fixtures helpers ─────────────────────────────────────────────

def _make_user(db_session, user_id=_GW_USER, email="user@gw.test"):
    u = User(id=user_id, email=email, display_name="GW User", kind="client", status="active")
    db_session.add(u)
    db_session.commit()
    return u


def _make_session(db_session, user_id=_GW_USER, session_id="s-gw"):
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
    user_id=_GW_USER,
    env_id=_GW_ENV,
    upstream="upstream.cfargotunnel.com",
    service_token_ref=None,
):
    org = Organization(id=_GW_ORG, name="GW Org", slug="gw-org")
    proj = Project(id=_GW_PROJ, organization_id=_GW_ORG, name="GW Proj", slug="gw-proj")
    env = Environment(
        id=env_id,
        project_id=_GW_PROJ,
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
        id=_GW_GRANT,
        user_id=user_id,
        organization_id=_GW_ORG,
        role="client_member",
    )
    db_session.add_all([org, proj, env, grant])
    db_session.commit()
    return env


# ── Tests 401 ────────────────────────────────────────────────────

def test_gateway_requires_session(client):
    """Sans cookie de session, le gateway retourne 401."""
    res = client.get(f"/gateway/{_GW_ENV}/")
    assert res.status_code == 401


# ── Tests 404 ────────────────────────────────────────────────────

def test_gateway_unknown_environment(client, db_session):
    """Environnement inexistant → 404."""
    _make_user(db_session)
    _make_session(db_session)
    client.cookies.set("devgate_session", "s-gw")

    # Use a valid UUID that doesn't exist in DB → should return 404
    res = client.get(f"/gateway/{_GW_ENV_NONEXISTENT}/")
    assert res.status_code == 404


# ── Tests 403 ────────────────────────────────────────────────────

def test_gateway_forbidden_no_grant(client, db_session):
    """Environnement connu mais l'utilisateur n'a pas de grant → 403."""
    _make_user(db_session)
    _make_session(db_session)

    # Créer l'env sans grant pour cet utilisateur
    org = Organization(id=_GW_ORG_NOGRANT, name="Other Org", slug="other-org")
    proj = Project(id=_GW_PROJ_NOGRANT, organization_id=_GW_ORG_NOGRANT, name="P", slug="p")
    env = Environment(
        id=_GW_ENV_NOGRANT,
        project_id=_GW_PROJ_NOGRANT,
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
    res = client.get(f"/gateway/{_GW_ENV_NOGRANT}/")
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
    res = client.get(f"/gateway/{_GW_ENV}/")

    assert res.status_code == 200
    assert b"Hello from upstream" in res.content


@respx.mock
def test_gateway_proxies_subpath(client, db_session):
    """Le path complet est transmis à l'upstream."""
    _make_user(db_session)
    _make_session(db_session)
    _make_env(db_session)

    respx.get(url__regex=r"https://upstream\.cfargotunnel\.com/api/data.*").mock(
        return_value=httpx.Response(200, json={"key": "value"})
    )

    client.cookies.set("devgate_session", "s-gw")
    res = client.get(f"/gateway/{_GW_ENV}/api/data")

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
    client.get(f"/gateway/{_GW_ENV}/")

    event = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.event_type == "gateway.resource.accessed")
        .first()
    )
    assert event is not None
    assert event.actor_user_id == _GW_USER
    assert event.target_id == _GW_ENV


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
    res = client.get(f"/gateway/{_GW_ENV}/")

    assert res.status_code == 502


@respx.mock
def test_gateway_injects_cf_service_token(client, db_session, monkeypatch):
    """Quand service_token_ref est défini, les headers CF-Access-* sont injectés via SecretStore."""
    import base64
    import json as _json

    TEST_MASTER_KEY = base64.b64encode(b"a" * 32).decode()
    monkeypatch.setenv("DEVGATE_MASTER_KEY", TEST_MASTER_KEY)

    _make_user(db_session)
    _make_session(db_session)

    # Stocker le token dans le SecretStore avant de créer l'env
    from app.modules.secrets.store import EncryptedDatabaseSecretStore
    store = EncryptedDatabaseSecretStore(master_key_b64=TEST_MASTER_KEY, db=db_session)
    payload = _json.dumps({"client_id": "test-client-id", "client_secret": "test-client-secret"})
    ref = store.put("cloudflare_service_token", payload, owner_type="environment", owner_id=_GW_ENV)
    db_session.commit()

    _make_env(db_session, service_token_ref=ref)

    captured_headers: dict = {}

    def capture(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(200, content=b"ok")

    respx.get("https://upstream.cfargotunnel.com/").mock(side_effect=capture)

    client.cookies.set("devgate_session", "s-gw")
    client.get(f"/gateway/{_GW_ENV}/")

    assert captured_headers.get("cf-access-client-id") == "test-client-id"
    assert captured_headers.get("cf-access-client-secret") == "test-client-secret"


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
    client.get(f"/gateway/{_GW_ENV}/")

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
    client.get(f"/gateway/{_GW_ENV}/")

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
    client.get(f"/gateway/{_GW_ENV}/")

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
    res = client.get(f"/gateway/{_GW_ENV}/")
    assert res.status_code == 502

    event = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.event_type == "gateway.request.failed")
        .first()
    )
    assert event is not None
    assert event.metadata_json["reason"] == "upstream_unavailable"
