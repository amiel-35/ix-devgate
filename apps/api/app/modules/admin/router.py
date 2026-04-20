"""
Back-office agence — CRUD clients, environnements, accès, audit.
Toutes les routes exigent agency_admin.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.modules.admin.schemas import (
    AuditEventResponse,
    CreateAccessGrantRequest,
    CreateEnvironmentRequest,
    CreateOrganizationRequest,
)
from app.modules.audit.service import audit
from app.shared.deps import require_agency_admin
from app.shared.exceptions import NotFoundException
from app.shared.models import (
    AccessGrant, AuditEvent, Environment,
    Organization, Project, User,
)

router = APIRouter(dependencies=[Depends(require_agency_admin)])


# ── Organisations ─────────────────────────────────────────────────

@router.get("/organizations")
def list_organizations(db: DbSession = Depends(get_db)):
    return db.query(Organization).all()


@router.post("/organizations", status_code=201)
def create_organization(
    body: CreateOrganizationRequest,
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    org = Organization(**body.model_dump())
    db.add(org)
    db.commit()
    audit(db, actor_user_id=admin.id, event_type="admin.organization.created",
          target_type="organization", target_id=org.id)
    db.commit()
    return org


# ── Environnements ────────────────────────────────────────────────

@router.get("/environments")
def list_environments(db: DbSession = Depends(get_db)):
    # Ne jamais retourner upstream_hostname ni service_token_ref
    envs = db.query(Environment).all()
    return [
        {
            "id": e.id,
            "project_id": e.project_id,
            "name": e.name,
            "slug": e.slug,
            "kind": e.kind,
            "public_hostname": e.public_hostname,
            "requires_app_auth": e.requires_app_auth,
            "status": e.status,
            "cloudflare_tunnel_id": e.cloudflare_tunnel_id,
            "cloudflare_access_app_id": e.cloudflare_access_app_id,
        }
        for e in envs
    ]


@router.post("/environments", status_code=201)
def create_environment(
    body: CreateEnvironmentRequest,
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    env = Environment(**body.model_dump())
    db.add(env)
    db.commit()
    audit(db, actor_user_id=admin.id, event_type="admin.environment.created",
          target_type="environment", target_id=env.id)
    db.commit()
    return {"id": env.id}


# ── Accès (grants) ────────────────────────────────────────────────

@router.get("/access-grants")
def list_grants(db: DbSession = Depends(get_db)):
    return db.query(AccessGrant).all()


@router.post("/access-grants", status_code=201)
def create_grant(
    body: CreateAccessGrantRequest,
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        # Créer l'utilisateur à la volée
        user = User(email=body.email, display_name=body.display_name, kind="client")
        db.add(user)
        db.flush()

    grant = AccessGrant(user_id=user.id, organization_id=body.organization_id, role=body.role)
    db.add(grant)
    db.commit()
    audit(db, actor_user_id=admin.id, event_type="admin.access_grant.created",
          target_type="access_grant", target_id=grant.id,
          metadata={"email": body.email, "role": body.role})
    db.commit()
    return {"id": grant.id}


@router.delete("/access-grants/{grant_id}", status_code=204)
def revoke_grant(
    grant_id: str,
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    from datetime import datetime, timezone
    grant = db.query(AccessGrant).filter(AccessGrant.id == grant_id).first()
    if not grant:
        raise NotFoundException()
    grant.revoked_at = datetime.now(tz=timezone.utc)
    db.commit()
    audit(db, actor_user_id=admin.id, event_type="admin.access_grant.revoked",
          target_type="access_grant", target_id=grant_id)
    db.commit()


# ── Audit ─────────────────────────────────────────────────────────

@router.get("/audit-events", response_model=list[AuditEventResponse])
def list_audit_events(
    limit: int = 50,
    offset: int = 0,
    db: DbSession = Depends(get_db),
):
    events = (
        db.query(AuditEvent)
        .order_by(AuditEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        AuditEventResponse(
            id=e.id,
            actor_user_id=e.actor_user_id,
            event_type=e.event_type,
            target_type=e.target_type,
            target_id=e.target_id,
            metadata_json=e.metadata_json,
            created_at=e.created_at.isoformat(),
        )
        for e in events
    ]
