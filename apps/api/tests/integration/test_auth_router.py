from app.modules.email import get_email_provider, override_email_provider
from app.modules.email.provider import FakeEmailProvider
from app.shared.models import User


def _make_user(db_session, email="user@example.com"):
    user = User(email=email, display_name="U", kind="client", status="active")
    db_session.add(user)
    db_session.commit()
    return user


def test_start_magic_link_returns_200(client, db_session):
    override_email_provider(FakeEmailProvider())
    _make_user(db_session)

    res = client.post("/auth/start", json={"email": "user@example.com"})

    assert res.status_code == 200
    assert res.json() == {"ok": True, "method": "magic_link"}


def test_start_otp_returns_200(client, db_session):
    override_email_provider(FakeEmailProvider())
    _make_user(db_session)

    res = client.post("/auth/start", json={"email": "user@example.com", "method": "otp"})

    assert res.status_code == 200
    assert res.json() == {"ok": True, "method": "otp"}
    assert get_email_provider().sent[0]["kind"] == "otp"


def test_start_invalid_email_returns_422(client):
    res = client.post("/auth/start", json={"email": "not-an-email"})
    assert res.status_code == 422


def test_verify_valid_token_sets_cookie(client, db_session):
    override_email_provider(FakeEmailProvider())
    _make_user(db_session)
    client.post("/auth/start", json={"email": "user@example.com"})
    token = get_email_provider().sent[0]["link"].split("token=")[1]

    res = client.post("/auth/verify", json={"token": token})

    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["session_created"] is True
    assert body["redirect_to"] == "/portal"
    assert "devgate_session" in res.cookies


def test_verify_invalid_token_returns_404(client):
    res = client.post("/auth/verify", json={"token": "invalid"})
    assert res.status_code == 404


def test_logout_clears_cookie(client, db_session):
    override_email_provider(FakeEmailProvider())
    _make_user(db_session)
    client.post("/auth/start", json={"email": "user@example.com"})
    token = get_email_provider().sent[0]["link"].split("token=")[1]
    client.post("/auth/verify", json={"token": token})

    res = client.post("/auth/logout")

    assert res.status_code == 200


def test_inactive_user_is_rejected(client, db_session):
    """Un user inactif doit recevoir 401 même avec une session valide."""
    from app.shared.models import User, Session as DevSession
    import uuid, datetime
    user = User(
        id=str(uuid.uuid4()),
        email="inactive@example.com",
        kind="client",
        status="inactive",
    )
    db_session.add(user)
    session = DevSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=7),
    )
    db_session.add(session)
    db_session.commit()

    response = client.post(
        "/auth/logout",
        cookies={"devgate_session": session.id},
    )
    assert response.status_code == 401, (
        f"Un user inactif doit être rejeté, got {response.status_code}"
    )


def test_logout_revokes_session_in_db(client, db_session):
    """Après logout, la session doit être supprimée en base."""
    from app.shared.models import User, Session as DevSession
    import uuid, datetime
    user = User(id=str(uuid.uuid4()), email="logout-test@example.com",
                kind="client", status="active")
    db_session.add(user)
    session = DevSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=7),
    )
    db_session.add(session)
    db_session.commit()

    response = client.post(
        "/auth/logout",
        cookies={"devgate_session": session.id},
    )
    assert response.status_code == 200

    remaining = db_session.query(DevSession).filter(DevSession.id == session.id).first()
    assert remaining is None, "La session doit être supprimée en base après logout"


def test_start_returns_429_over_rate_limit(client, db_session):
    override_email_provider(FakeEmailProvider())
    _make_user(db_session)

    # login_start_limiter is 5 req / 600s per IP+email
    for _ in range(5):
        res = client.post("/auth/start", json={"email": "user@example.com"})
        assert res.status_code == 200

    res = client.post("/auth/start", json={"email": "user@example.com"})
    assert res.status_code == 429


def test_verify_rate_limited(client, db_session, monkeypatch):
    """POST /auth/verify retourne 429 après trop de tentatives depuis la même IP."""
    from app.modules.auth import rate_limit as rl_mod
    from app.modules.auth.rate_limit import RateLimiter

    # Remplace le limiter par un limiter frais max=2 pour accélérer le test
    monkeypatch.setattr(rl_mod, "login_verify_limiter", RateLimiter(max_requests=2, window_seconds=300))

    for _ in range(2):
        client.post("/auth/verify", json={"token": "wrong-token"})

    res = client.post("/auth/verify", json={"token": "wrong-token"})
    assert res.status_code == 429
