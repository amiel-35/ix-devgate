"""Tests unitaires — module auth."""
import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.modules.auth.service import _hash_token, verify_token
from app.shared.exceptions import ChallengeAlreadyUsedException, ChallengeExpiredException
from app.shared.models import LoginChallenge, Session, User


def make_db():
    return MagicMock()


def test_hash_token_is_deterministic():
    assert _hash_token("abc") == _hash_token("abc")


def test_hash_token_differs():
    assert _hash_token("abc") != _hash_token("xyz")


def test_verify_token_expired():
    token = "test-token"
    hashed = _hash_token(token)

    challenge = LoginChallenge(
        id="c1",
        user_id="u1",
        type="magic_link",
        hashed_token=hashed,
        expires_at=datetime.now(tz=timezone.utc) - timedelta(minutes=1),
        used_at=None,
        attempt_count=0,
    )

    db = make_db()
    db.query.return_value.filter.return_value.first.return_value = challenge

    with pytest.raises(ChallengeExpiredException):
        verify_token(token, db)


def test_verify_token_already_used():
    token = "test-token"
    hashed = _hash_token(token)

    challenge = LoginChallenge(
        id="c1",
        user_id="u1",
        type="magic_link",
        hashed_token=hashed,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(minutes=10),
        used_at=datetime.now(tz=timezone.utc),  # déjà utilisé
        attempt_count=1,
    )

    db = make_db()
    db.query.return_value.filter.return_value.first.return_value = challenge

    with pytest.raises(ChallengeAlreadyUsedException):
        verify_token(token, db)
