"""
Gateway DevGate — couche explicite, pas un bricolage de controller.

Règles critiques :
- vérifie session ET grant avant de proxifier
- injecte les credentials Cloudflare Access service token
- ne renvoie jamais l'upstream_hostname ni le service_token au navigateur
- distingue : non autorisé / ressource introuvable / upstream KO
"""
from datetime import timezone

import httpx
from sqlalchemy.orm import Session as DbSession

from app.modules.audit.service import audit
from app.shared.exceptions import (
    ForbiddenException, NotFoundException, UpstreamUnavailableException,
)
from app.shared.models import AccessGrant, Environment, Project, User


def resolve_environment(env_id: str, user: User, db: DbSession) -> Environment:
    """Vérifie que l'utilisateur a accès à l'environnement et retourne sa config."""
    env = db.query(Environment).filter(Environment.id == env_id).first()
    if not env:
        raise NotFoundException("Environnement introuvable")

    project = db.query(Project).filter(Project.id == env.project_id).first()
    if not project:
        raise NotFoundException()

    # Vérification du grant par client (v1 : par organisation)
    grant = (
        db.query(AccessGrant)
        .filter(
            AccessGrant.user_id == user.id,
            AccessGrant.organization_id == project.organization_id,
            AccessGrant.revoked_at.is_(None),
        )
        .first()
    )
    if not grant:
        raise ForbiddenException("Accès non autorisé à cet environnement")

    return env


def _get_service_token(token_ref: str) -> tuple[str, str]:
    """Récupère le service token Cloudflare depuis le secret store.
    En v1 : depuis les variables d'environnement.
    """
    import os
    client_id = os.environ.get(f"CF_SERVICE_TOKEN_{token_ref}_ID", "")
    client_secret = os.environ.get(f"CF_SERVICE_TOKEN_{token_ref}_SECRET", "")
    return client_id, client_secret


async def proxy_request(
    env: Environment,
    method: str,
    path: str,
    headers: dict,
    body: bytes | None,
    user: User,
    db: DbSession,
) -> httpx.Response:
    """Proxifie la requête vers l'upstream Cloudflare protégé."""
    if not env.upstream_hostname:
        raise UpstreamUnavailableException("Upstream non configuré")

    upstream_url = f"https://{env.upstream_hostname}{path}"

    # Headers vers l'upstream :
    # - on retire host, cookie (ne pas fuiter la session DevGate) et accept-encoding
    # - on demande du contenu non compressé (identity) pour servir directement le navigateur
    # - on ajoute X-DevGate-User pour tracabilité upstream
    proxy_headers = {
        k: v for k, v in headers.items()
        if k.lower() not in ("host", "cookie", "accept-encoding")
    }
    proxy_headers["Accept-Encoding"] = "identity"
    proxy_headers["X-DevGate-User"] = user.id

    if env.service_token_ref:
        cf_client_id, cf_client_secret = _get_service_token(env.service_token_ref)
        if cf_client_id:
            proxy_headers["CF-Access-Client-Id"] = cf_client_id
        if cf_client_secret:
            proxy_headers["CF-Access-Client-Secret"] = cf_client_secret

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.request(
                method=method,
                url=upstream_url,
                headers=proxy_headers,
                content=body,
            )
    except httpx.ConnectError as e:
        raise UpstreamUnavailableException(f"Impossible de joindre l'upstream : {e}") from e
    except httpx.TimeoutException as e:
        raise UpstreamUnavailableException("L'upstream n'a pas répondu à temps") from e

    audit(
        db,
        actor_user_id=user.id,
        event_type="gateway.resource.accessed",
        target_type="environment",
        target_id=env.id,
        metadata={"status_code": response.status_code, "path": path},
    )
    db.commit()

    return response
