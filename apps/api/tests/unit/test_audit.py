from app.modules.audit.service import audit
from app.shared.models import AuditEvent


def test_audit_creates_event_with_all_fields(db_session):
    event = audit(
        db_session,
        event_type="login.session.created",
        actor_user_id="u1",
        target_type="session",
        target_id="s1",
        metadata={"ip": "1.2.3.4"},
    )
    db_session.commit()

    saved = db_session.query(AuditEvent).filter(AuditEvent.id == event.id).first()
    assert saved is not None
    assert saved.event_type == "login.session.created"
    assert saved.actor_user_id == "u1"
    assert saved.target_type == "session"
    assert saved.target_id == "s1"
    assert saved.metadata_json == {"ip": "1.2.3.4"}


def test_audit_minimal_fields(db_session):
    event = audit(db_session, event_type="admin.organization.created")
    db_session.commit()
    saved = db_session.query(AuditEvent).filter(AuditEvent.id == event.id).first()
    assert saved.event_type == "admin.organization.created"
    assert saved.actor_user_id is None
    assert saved.metadata_json is None
