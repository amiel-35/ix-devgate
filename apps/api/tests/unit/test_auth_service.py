from datetime import datetime, timedelta, timezone

import pytest

from app.modules.auth.service import _hash_token, start_login, verify_token
from app.modules.email import get_email_provider, override_email_provider
from app.modules.email.provider import FakeEmailProvider
from app.shared.exceptions import (
    ChallengeAlreadyUsedException,
    ChallengeExpiredException,
    NotFoundException,
)
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


def test_verify_token_creates_session_and_marks_challenge_used(db_session):
    override_email_provider(FakeEmailProvider())
    user = _make_user(db_session)
    start_login(user.email, db_session)
    provider = get_email_provider()
    link = provider.sent[0]["link"]
    token = link.split("token=")[1]

    session = verify_token(token, db_session)

    assert session.user_id == user.id
    # session expires ~7 days out
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    assert expires_at > datetime.now(tz=timezone.utc) + timedelta(days=6)

    challenge = db_session.query(LoginChallenge).filter(LoginChallenge.user_id == user.id).first()
    assert challenge.used_at is not None

    db_session.refresh(user)
    assert user.last_login_at is not None


def test_verify_token_invalid_raises_not_found(db_session):
    with pytest.raises(NotFoundException):
        verify_token("no-such-token", db_session)


def test_verify_token_expired_raises(db_session):
    user = _make_user(db_session)
    challenge = LoginChallenge(
        user_id=user.id,
        type="magic_link",
        hashed_token=_hash_token("expired-token"),
        expires_at=datetime.now(tz=timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(challenge)
    db_session.commit()

    with pytest.raises(ChallengeExpiredException):
        verify_token("expired-token", db_session)


def test_verify_token_already_used_raises(db_session):
    user = _make_user(db_session)
    challenge = LoginChallenge(
        user_id=user.id,
        type="magic_link",
        hashed_token=_hash_token("used-token"),
        expires_at=datetime.now(tz=timezone.utc) + timedelta(minutes=10),
        used_at=datetime.now(tz=timezone.utc),
    )
    db_session.add(challenge)
    db_session.commit()

    with pytest.raises(ChallengeAlreadyUsedException):
        verify_token("used-token", db_session)


def test_verify_token_audits_session_creation(db_session):
    override_email_provider(FakeEmailProvider())
    user = _make_user(db_session)
    start_login(user.email, db_session)
    token = get_email_provider().sent[0]["link"].split("token=")[1]

    session = verify_token(token, db_session)

    events = db_session.query(AuditEvent).filter(
        AuditEvent.event_type == "login.session.created",
        AuditEvent.target_id == session.id,
    ).all()
    assert len(events) == 1
