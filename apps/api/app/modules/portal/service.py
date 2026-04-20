"""
Module portal — liste des environnements accessibles par l'utilisateur.
Accès v1 : par client (AccessGrant sur l'organisation).
"""
from datetime import timezone

from sqlalchemy.orm import Session as DbSession

from app.shared.models import (
    AccessGrant, Environment, Organization,
    Project, Session, TunnelHealthSnapshot, User,
)


def get_environments_for_user(user: User, db: DbSession) -> list[dict]:
    """Retourne les environnements accessibles via les grants actifs de l'utilisateur."""
    active_grants = (
        db.query(AccessGrant)
        .filter(
            AccessGrant.user_id == user.id,
            AccessGrant.revoked_at.is_(None),
        )
        .all()
    )

    org_ids = [g.organization_id for g in active_grants]
    if not org_ids:
        return []

    environments = (
        db.query(Environment, Project, Organization)
        .join(Project, Environment.project_id == Project.id)
        .join(Organization, Project.organization_id == Organization.id)
        .filter(
            Organization.id.in_(org_ids),
            Environment.status == "active",
        )
        .all()
    )

    result = []
    for env, project, org in environments:
        latest_health = (
            db.query(TunnelHealthSnapshot)
            .filter(TunnelHealthSnapshot.environment_id == env.id)
            .order_by(TunnelHealthSnapshot.observed_at.desc())
            .first()
        )
        status = latest_health.status if latest_health else "unknown"

        result.append({
            "id": env.id,
            "organization_name": org.name,
            "project_name": project.name,
            "environment_name": env.name,
            "kind": env.kind,
            "url": f"https://{env.public_hostname}",
            "requires_app_auth": env.requires_app_auth,
            "status": status,
        })

    return result
