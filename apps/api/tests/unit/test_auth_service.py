from datetime import datetime, timezone

from app.modules.auth.service import start_login
from app.modules.email import get_email_provider, override_email_provider
from app.modules.email.provider import FakeEmailProvider
from app.shared.models import AuditEvent, LoginChallenge, User


def _make_user(db_session, email="user@example.com", kind="client"):
    user = User(email=email, display_name="Test", kind=kind, status="active")
    db_session.add(user)
    db_session.commit()
    return user


def test_start_login_known_email_creates_challenge(db_session):
    fake = FakeEmailProvider()
    override_email_provider(fake)
    user = _make_user(db_session)

    result = start_login("user@example.com", db_session)

    assert result == {"ok": True, "method": "magic_link"}
    challenges = db_session.query(LoginChallenge).filter(LoginChallenge.user_id == user.id).all()
    assert len(challenges) == 1
    assert challenges[0].type == "magic_link"
    assert challenges[0].used_at is None
    expires_at = challenges[0].expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    assert expires_at > datetime.now(tz=timezone.utc)

    assert len(fake.sent) == 1
    assert fake.sent[0]["kind"] == "magic_link"
    assert fake.sent[0]["to"] == "user@example.com"


def test_start_login_unknown_email_returns_ok_but_no_challenge(db_session):
    """Anti-enumeration : the response is identical for known and unknown emails."""
    fake = FakeEmailProvider()
    override_email_provider(fake)

    result = start_login("unknown@example.com", db_session)

    assert result == {"ok": True, "method": "magic_link"}
    assert db_session.query(LoginChallenge).count() == 0
    assert fake.sent == []
    events = db_session.query(AuditEvent).filter(
        AuditEvent.event_type == "login.start.unknown_email"
    ).all()
    assert len(events) == 1


def test_start_login_audits_request(db_session):
    override_email_provider(FakeEmailProvider())
    user = _make_user(db_session)

    start_login(user.email, db_session)

    events = db_session.query(AuditEvent).filter(
        AuditEvent.event_type == "login.magic_link.requested",
        AuditEvent.actor_user_id == user.id,
    ).all()
    assert len(events) == 1


def test_start_login_otp_method_creates_otp_challenge(db_session):
    fake = FakeEmailProvider()
    override_email_provider(fake)
    user = _make_user(db_session)

    result = start_login(user.email, db_session, method="otp")

    assert result == {"ok": True, "method": "otp"}
    challenges = db_session.query(LoginChallenge).filter(LoginChallenge.user_id == user.id).all()
    assert len(challenges) == 1
    assert challenges[0].type == "otp"
    assert fake.sent[0]["kind"] == "otp"
    # OTP is 6 digits
    assert len(fake.sent[0]["code"]) == 6
    assert fake.sent[0]["code"].isdigit()
