"""Tests unitaires — module audit."""
from unittest.mock import MagicMock

from app.modules.audit.service import audit
from app.shared.models import AuditEvent


def test_audit_creates_event():
    db = MagicMock()
    event = audit(
        db,
        event_type="login.session.created",
        actor_user_id="u1",
        target_type="session",
        target_id="s1",
        metadata={"ip": "1.2.3.4"},
    )
    db.add.assert_called_once()
    db.flush.assert_called_once()
    assert event.event_type == "login.session.created"
    assert event.actor_user_id == "u1"


def test_audit_minimal_fields():
    db = MagicMock()
    event = audit(db, event_type="admin.organization.created")
    assert event.event_type == "admin.organization.created"
    assert event.actor_user_id is None
