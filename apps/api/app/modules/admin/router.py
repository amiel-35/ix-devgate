"""
Back-office agence — CRUD clients, projets, environnements, accès, audit, stats.
Toutes les routes exigent agency_admin.
"""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession, joinedload

from app.database import get_db
from app.modules.admin.schemas import (
    AuditEventResponse,
    CreateAccessGrantRequest,
    CreateEnvironmentRequest,
    CreateOrganizationRequest,
    CreateProjectRequest,
    StatsResponse,
)
from app.modules.audit.service import audit
from app.shared.deps import require_agency_admin
from app.shared.exceptions import NotFoundException
from app.shared.models import (
    AccessGrant,
    AuditEvent,
    Environment,
    Organization,
    Project,
    User,
)

router = APIRouter(dependencies=[Depends(require_agency_admin)])


# ── Stats ─────────────────────────────────────────────────────────

@router.get("/stats", response_model=StatsResponse)
def get_stats(db: DbSession = Depends(get_db)):
    today_start = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return StatsResponse(
        active_orgs=db.query(Organization).count(),
        active_envs=db.query(Environment).filter(Environment.status == "active").count(),
        active_users=db.query(User).filter(User.status == "active").count(),
        events_today=db.query(AuditEvent).filter(AuditEvent.created_at >= today_start).count(),
    )


# ── Organisations ─────────────────────────────────────────────────

@router.get("/organizations")
def list_organizations(db: DbSession = Depends(get_db)):
    orgs = db.query(Organization).all()
    result = []
    for org in orgs:
        env_count = (
            db.query(Environment)
            .join(Project)
            .filter(Project.organization_id == org.id)
            .count()
        )
        user_count = (
            db.query(AccessGrant)
            .filter(
                AccessGrant.organization_id == org.id,
                AccessGrant.revoked_at.is_(None),
            )
            .count()
        )
        result.append({
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "branding_name": org.branding_name,
            "support_email": org.support_email,
            "env_count": env_count,
            "user_count": user_count,
        })
    return result


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
    return {"id": org.id}


# ── Projets ───────────────────────────────────────────────────────

@router.get("/projects")
def list_projects(org_id: str | None = None, db: DbSession = Depends(get_db)):
    q = db.query(Project)
    if org_id:
        q = q.filter(Project.organization_id == org_id)
    return [
        {"id": p.id, "organization_id": p.organization_id, "name": p.name, "slug": p.slug}
        for p in q.all()
    ]


@router.post("/projects", status_code=201)
def create_project(
    body: CreateProjectRequest,
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    org = db.query(Organization).filter(Organization.id == body.organization_id).first()
    if not org:
        raise NotFoundException()
    project = Project(**body.model_dump())
    db.add(project)
    db.commit()
    audit(db, actor_user_id=admin.id, event_type="admin.project.created",
          target_type="project", target_id=project.id)
    db.commit()
    return {"id": project.id}


# ── Environnements ────────────────────────────────────────────────

@router.get("/environments")
def list_environments(db: DbSession = Depends(get_db)):
    envs = (
        db.query(Environment)
        .options(joinedload(Environment.project).joinedload(Project.organization))
        .all()
    )
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
            "org_name": e.project.organization.name,
            "project_name": e.project.name,
        }
        for e in envs
    ]


@router.post("/environments", status_code=201)
def create_environment(
    body: CreateEnvironmentRequest,
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    project = db.query(Project).filter(Project.id == body.project_id).first()
    if not project:
        raise NotFoundException()
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
    grants = (
        db.query(AccessGrant)
        .options(joinedload(AccessGrant.user), joinedload(AccessGrant.organization))
        .all()
    )
    return [
        {
            "id": g.id,
            "user_id": g.user_id,
            "user_email": g.user.email,
            "organization_id": g.organization_id,
            "org_name": g.organization.name,
            "role": g.role,
            "created_at": g.created_at.isoformat(),
            "revoked_at": g.revoked_at.isoformat() if g.revoked_at else None,
        }
        for g in grants
    ]


@router.post("/access-grants", status_code=201)
def create_grant(
    body: CreateAccessGrantRequest,
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    org = db.query(Organization).filter(Organization.id == body.organization_id).first()
    if not org:
        raise NotFoundException()

    user = db.query(User).filter(User.email == body.email).first()
    if not user:
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
    grant = db.query(AccessGrant).filter(AccessGrant.id == grant_id).first()
    if not grant:
        raise NotFoundException()
    if grant.revoked_at is not None:
        return  # Déjà révoqué, idempotent
    grant.revoked_at = datetime.now(tz=timezone.utc)
    db.commit()
    audit(db, actor_user_id=admin.id, event_type="admin.access_grant.revoked",
          target_type="access_grant", target_id=grant_id)
    db.commit()


# ── Audit ─────────────────────────────────────────────────────────

@router.get("/audit-events", response_model=list[AuditEventResponse])
def list_audit_events(
    limit: int = Query(50, le=200),
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
