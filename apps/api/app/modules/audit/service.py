"""
Module audit — événements structurés, append-only.
L'audit n'est pas du logging opportuniste.
"""
from sqlalchemy.orm import Session as DbSession

from app.shared.models import AuditEvent


def audit(
    db: DbSession,
    event_type: str,
    actor_user_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_user_id=actor_user_id,
        event_type=event_type,
        target_type=target_type,
        target_id=target_id,
        metadata_json=metadata,
    )
    db.add(event)
    db.flush()  # ID dispo sans commit complet
    return event
