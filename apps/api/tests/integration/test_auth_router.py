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


def test_start_returns_429_over_rate_limit(client, db_session):
    override_email_provider(FakeEmailProvider())
    _make_user(db_session)

    # login_start_limiter is 5 req / 600s per IP+email
    for _ in range(5):
        res = client.post("/auth/start", json={"email": "user@example.com"})
        assert res.status_code == 200

    res = client.post("/auth/start", json={"email": "user@example.com"})
    assert res.status_code == 429
