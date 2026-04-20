"""Tests unitaires — logique d'accès par client (grants)."""
from unittest.mock import MagicMock

import pytest

from app.modules.portal.service import get_environments_for_user
from app.shared.models import AccessGrant, User


def test_no_grants_returns_empty():
    user = User(id="u1", email="test@example.com", kind="client")
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []

    result = get_environments_for_user(user, db)
    assert result == []


def test_revoked_grant_not_included():
    """Un grant révoqué ne doit pas donner accès aux ressources."""
    from datetime import datetime, timezone
    user = User(id="u1", email="test@example.com", kind="client")
    db = MagicMock()

    revoked_grant = AccessGrant(
        id="g1",
        user_id="u1",
        organization_id="org1",
        role="client_member",
        revoked_at=datetime.now(tz=timezone.utc),
    )
    db.query.return_value.filter.return_value.all.return_value = [revoked_grant]

    # Le service filtre revoked_at IS NULL en base
    # Ici on teste que s'il n'y a pas de grants actifs, la liste est vide
    result = get_environments_for_user(user, db)
    assert result == []
