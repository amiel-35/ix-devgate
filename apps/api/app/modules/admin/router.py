"""
Back-office agence — CRUD clients, projets, environnements, accès, audit, stats.
Toutes les routes exigent agency_admin.
"""
import json
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession, joinedload

from app.config import settings
from app.modules.cloudflare.client import CFClient
from app.modules.cloudflare.provisioner import ProvisioningError, run_provisioning_job
from app.modules.cloudflare.sync import sync_tunnels
from app.modules.gateway.health import check_environment_health

from app.database import get_db
from app.modules.admin.schemas import (
    AssignTunnelRequest,
    AuditEventResponse,
    CreateAccessGrantRequest,
    CreateEnvironmentRequest,
    CreateOrganizationRequest,
    CreateProjectRequest,
    StatsResponse,
    StoreServiceTokenRequest,
)
from app.modules.audit.service import audit
from app.modules.secrets.deps import get_secret_store
from app.modules.secrets.store import SecretNotFoundError
from app.shared.deps import require_agency_admin
from app.shared.exceptions import NotFoundException
from app.shared.models import (
    AccessGrant,
    AuditEvent,
    DiscoveredTunnel,
    Environment,
    Organization,
    Project,
    ProvisioningJob,
    TunnelHealthSnapshot,
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

    # Two aggregate queries instead of 2N individual ones
    env_counts: dict[str, int] = dict(
        db.query(Project.organization_id, func.count(Environment.id))
        .join(Environment, Environment.project_id == Project.id, isouter=True)
        .group_by(Project.organization_id)
        .all()
    )
    user_counts: dict[str, int] = dict(
        db.query(AccessGrant.organization_id, func.count(AccessGrant.id))
        .filter(AccessGrant.revoked_at.is_(None))
        .group_by(AccessGrant.organization_id)
        .all()
    )

    return [
        {
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "branding_name": org.branding_name,
            "support_email": org.support_email,
            "env_count": env_counts.get(org.id, 0),
            "user_count": user_counts.get(org.id, 0),
        }
        for org in orgs
    ]


@router.post("/organizations", status_code=201)
def create_organization(
    body: CreateOrganizationRequest,
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    org = Organization(**body.model_dump())
    db.add(org)
    db.flush()
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
    db.flush()
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

    # Dernier snapshot de santé par environnement (une seule requête groupée)
    env_ids = [e.id for e in envs]
    snap_by_env: dict = {}
    if env_ids:
        latest_subq = (
            db.query(
                TunnelHealthSnapshot.environment_id,
                func.max(TunnelHealthSnapshot.observed_at).label("max_ts"),
            )
            .filter(TunnelHealthSnapshot.environment_id.in_(env_ids))
            .group_by(TunnelHealthSnapshot.environment_id)
            .subquery()
        )
        snaps = (
            db.query(TunnelHealthSnapshot)
            .join(
                latest_subq,
                (TunnelHealthSnapshot.environment_id == latest_subq.c.environment_id)
                & (TunnelHealthSnapshot.observed_at == latest_subq.c.max_ts),
            )
            .all()
        )
        snap_by_env = {s.environment_id: s for s in snaps}

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
            "org_name": e.project.organization.name,
            "project_name": e.project.name,
            "health_status": snap_by_env[e.id].status if e.id in snap_by_env else None,
            "health_latency_ms": (
                snap_by_env[e.id].metadata_json.get("latency_ms")
                if e.id in snap_by_env and snap_by_env[e.id].metadata_json
                else None
            ),
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
    db.flush()
    audit(db, actor_user_id=admin.id, event_type="admin.environment.created",
          target_type="environment", target_id=env.id)
    db.commit()
    return {"id": env.id}


@router.post("/environments/{env_id}/ping", status_code=200)
async def ping_environment(
    env_id: UUID,
    db: DbSession = Depends(get_db),
):
    """Déclenche un health check immédiat sur l'upstream d'un environnement.
    Retourne le statut observé. Ne contient jamais les credentials Cloudflare.
    """
    env = db.query(Environment).filter(Environment.id == str(env_id)).first()
    if not env:
        raise NotFoundException()
    snapshot = await check_environment_health(env, db)
    return {
        "environment_id": env.id,
        "status": snapshot.status,
        "observed_at": snapshot.observed_at.isoformat(),
        "latency_ms": snapshot.metadata_json.get("latency_ms") if snapshot.metadata_json else None,
    }


@router.put("/environments/{env_id}/service-token", status_code=200)
def store_service_token(
    env_id: UUID,
    body: StoreServiceTokenRequest,
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    """Stocke ou remplace le service token Cloudflare Access d'un environnement.
    Le token est chiffré en base — jamais stocké en clair.
    """
    env_id_str = str(env_id)
    env = db.query(Environment).filter(Environment.id == env_id_str).first()
    if not env:
        raise NotFoundException()

    secret_store = get_secret_store(db)

    # Révoquer l'ancien token si présent
    if env.service_token_ref:
        try:
            secret_store.revoke(env.service_token_ref)
        except SecretNotFoundError:
            pass  # Déjà absent, idempotent

    payload = json.dumps({"client_id": body.client_id, "client_secret": body.client_secret})
    ref = secret_store.put(
        secret_type="cloudflare_service_token",
        plaintext=payload,
        owner_type="environment",
        owner_id=env_id_str,
    )
    env.service_token_ref = ref

    audit(
        db,
        actor_user_id=admin.id,
        event_type="admin.service_token.stored",
        target_type="environment",
        target_id=env_id_str,
        metadata={"has_token": True},
    )
    db.commit()
    return {"ok": True}


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
    db.flush()
    audit(db, actor_user_id=admin.id, event_type="admin.access_grant.created",
          target_type="access_grant", target_id=grant.id,
          metadata={"email": body.email, "role": body.role})
    db.commit()
    return {"id": grant.id}


@router.delete("/access-grants/{grant_id}", status_code=204)
def revoke_grant(
    grant_id: UUID,
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    grant_id_str = str(grant_id)
    grant = db.query(AccessGrant).filter(AccessGrant.id == grant_id_str).first()
    if not grant:
        raise NotFoundException()
    if grant.revoked_at is not None:
        return  # Déjà révoqué, idempotent
    grant.revoked_at = datetime.now(tz=timezone.utc)
    db.flush()
    audit(db, actor_user_id=admin.id, event_type="admin.access_grant.revoked",
          target_type="access_grant", target_id=grant_id_str)
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


# ── Cloudflare ────────────────────────────────────────────────────

@router.post("/sync-tunnels", status_code=200)
def trigger_cf_sync(
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    """Déclenche manuellement la sync des tunnels CF.
    Nécessite CF_API_TOKEN et CF_ACCOUNT_ID configurés.
    """
    if not settings.CF_API_TOKEN or not settings.CF_ACCOUNT_ID:
        raise HTTPException(
            status_code=503,
            detail="CF_API_TOKEN ou CF_ACCOUNT_ID non configurés",
        )
    cf = CFClient(
        api_token=settings.CF_API_TOKEN,
        account_id=settings.CF_ACCOUNT_ID,
        zone_id=settings.CF_ZONE_ID,
    )
    return sync_tunnels(db, cf)


@router.get("/discovered-tunnels")
def list_discovered_tunnels(
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    """Liste tous les tunnels découverts, ordonnés par date de création décroissante."""
    tunnels = (
        db.query(DiscoveredTunnel)
        .order_by(DiscoveredTunnel.created_at.desc())
        .all()
    )
    return [
        {
            "id": t.id,
            "cloudflare_tunnel_id": t.cloudflare_tunnel_id,
            "name": t.name,
            "status": t.status,
            "last_seen_at": t.last_seen_at.isoformat() if t.last_seen_at else None,
        }
        for t in tunnels
    ]


def _get_cf_client_for_activate():
    """Crée le CFClient depuis la config. Séparé pour permettre le mock dans les tests."""
    if not settings.CF_API_TOKEN or not settings.CF_ACCOUNT_ID:
        raise HTTPException(
            status_code=503,
            detail="CF_API_TOKEN ou CF_ACCOUNT_ID non configurés",
        )
    return CFClient(
        api_token=settings.CF_API_TOKEN,
        account_id=settings.CF_ACCOUNT_ID,
        zone_id=settings.CF_ZONE_ID,
    )


@router.post("/discovered-tunnels/{tunnel_id}/assign", status_code=200)
def assign_tunnel_to_environment(
    tunnel_id: UUID,
    body: AssignTunnelRequest,
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    """Affecte un tunnel découvert à un environnement DevGate."""
    tunnel = db.query(DiscoveredTunnel).filter(DiscoveredTunnel.id == str(tunnel_id)).first()
    if not tunnel:
        raise NotFoundException()

    env = db.query(Environment).filter(Environment.id == body.environment_id).first()
    if not env:
        raise NotFoundException()

    tunnel.status = "assigned"
    env.cloudflare_tunnel_id = tunnel.cloudflare_tunnel_id
    env.upstream_hostname = f"{tunnel.cloudflare_tunnel_id}.cfargotunnel.com"
    env.discovered_tunnel_id = tunnel.id

    audit(
        db,
        actor_user_id=admin.id,
        event_type="admin.tunnel.assigned",
        target_type="environment",
        target_id=env.id,
        metadata={"tunnel_id": tunnel.cloudflare_tunnel_id, "tunnel_name": tunnel.name},
    )
    db.commit()
    return {"ok": True}


@router.post("/environments/{env_id}/activate", status_code=200)
def activate_environment(
    env_id: UUID,
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    """Lance le provisioning CF pour un environnement (ADR-001 saga).
    Nécessite : CF credentials configurés + tunnel assigné sur l'environnement.
    """
    env_id_str = str(env_id)
    env = db.query(Environment).filter(Environment.id == env_id_str).first()
    if not env:
        raise NotFoundException()

    if not env.cloudflare_tunnel_id:
        raise HTTPException(
            status_code=422,
            detail="Aucun tunnel assigné à cet environnement — assignez d'abord un DiscoveredTunnel",
        )

    cf = _get_cf_client_for_activate()
    secret_store = get_secret_store(db)

    job = ProvisioningJob(environment_id=env_id_str, state="pending")
    db.add(job)
    db.flush()

    try:
        final_state = run_provisioning_job(job, env, cf, secret_store, db)
    except ProvisioningError as e:
        return {"job_id": job.id, "state": job.state, "error": str(e)}

    audit(
        db,
        actor_user_id=admin.id,
        event_type="admin.environment.activated",
        target_type="environment",
        target_id=env_id_str,
        metadata={"job_id": job.id, "final_state": final_state},
    )
    db.commit()
    return {"job_id": job.id, "state": final_state}


# ── Gateway stats ─────────────────────────────────────────────────

@router.get("/gateway-stats")
def get_gateway_stats(db: DbSession = Depends(get_db)):
    """Stats des requêtes gateway sur les 24 dernières heures.

    Agrège les événements d'audit pour éviter un modèle supplémentaire.
    Acceptable pour v1 (volume faible). Ne filtre pas par environnement.
    """
    from datetime import timedelta
    since = datetime.now(tz=timezone.utc) - timedelta(hours=24)

    accessed = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.event_type == "gateway.resource.accessed",
            AuditEvent.created_at >= since,
        )
        .all()
    )

    upstream_unavailable = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.event_type == "gateway.request.failed",
            AuditEvent.created_at >= since,
        )
        .count()
    )

    total = len(accessed) + upstream_unavailable
    errors_5xx = sum(1 for e in accessed if e.metadata_json and e.metadata_json.get("is_5xx"))
    cf_refused = sum(1 for e in accessed if e.metadata_json and e.metadata_json.get("is_cf_refused"))
    latencies = [
        e.metadata_json["latency_ms"]
        for e in accessed
        if e.metadata_json and isinstance(e.metadata_json.get("latency_ms"), int)
    ]

    avg_latency_ms: int | None = None
    p95_latency_ms: int | None = None
    if latencies:
        avg_latency_ms = int(sum(latencies) / len(latencies))
        sorted_latencies = sorted(latencies)
        p95_idx = max(0, int(len(sorted_latencies) * 0.95) - 1)
        p95_latency_ms = sorted_latencies[p95_idx]

    return {
        "since_hours": 24,
        "total_requests": total,
        "errors_5xx": errors_5xx,
        "cf_refused": cf_refused,
        "upstream_unavailable": upstream_unavailable,
        "avg_latency_ms": avg_latency_ms,
        "p95_latency_ms": p95_latency_ms,
    }
