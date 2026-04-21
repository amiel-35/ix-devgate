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

    respx.get(url__regex=r"https://upstream\.cfargotunnel\.com/api/data.*").mock(
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
    """Quand service_token_ref est défini, les headers CF-Access-* sont injectés via SecretStore."""
    import base64
    import json as _json

    TEST_MASTER_KEY = base64.b64encode(b"devgate-test-key-32bytes-padding!").decode()
    monkeypatch.setenv("DEVGATE_MASTER_KEY", TEST_MASTER_KEY)

    _make_user(db_session)
    _make_session(db_session)

    # Stocker le token dans le SecretStore avant de créer l'env
    from app.modules.secrets.store import EncryptedDatabaseSecretStore
    store = EncryptedDatabaseSecretStore(master_key_b64=TEST_MASTER_KEY, db=db_session)
    payload = _json.dumps({"client_id": "test-client-id", "client_secret": "test-client-secret"})
    ref = store.put("cloudflare_service_token", payload, owner_type="environment", owner_id="env-gw")
    db_session.commit()

    _make_env(db_session, service_token_ref=ref)

    captured_headers: dict = {}

    def capture(request: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(200, content=b"ok")

    respx.get("https://upstream.cfargotunnel.com/").mock(side_effect=capture)

    client.cookies.set("devgate_session", "s-gw")
    client.get("/gateway/env-gw/")

    assert captured_headers.get("cf-access-client-id") == "test-client-id"
    assert captured_headers.get("cf-access-client-secret") == "test-client-secret"
