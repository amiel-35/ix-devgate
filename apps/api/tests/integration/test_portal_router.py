from datetime import datetime, timedelta, timezone

from app.shared.models import (
    AccessGrant,
    Environment,
    Organization,
    Project,
    Session as SessionModel,
    User,
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


# ── GET /me ──────────────────────────────────────────────────────


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


# ── GET /me/environments ─────────────────────────────────────────


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


# ── GET /me/sessions ─────────────────────────────────────────────


def test_sessions_returns_all_user_sessions(client, db_session):
    _make_user(db_session)
    _make_session(db_session, session_id="s-test")
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


# ── DELETE /me/sessions/{id} ─────────────────────────────────────


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

    # Le backend ignore silencieusement — la session doit encore exister
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
