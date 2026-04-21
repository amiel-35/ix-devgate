"""
Gateway DevGate — couche explicite, pas un bricolage de controller.

Règles critiques :
- vérifie session ET grant avant de proxifier
- injecte les credentials Cloudflare Access service token
- ne renvoie jamais l'upstream_hostname ni le service_token au navigateur
- distingue : non autorisé / ressource introuvable / upstream KO
"""
import json
import logging
import time
from datetime import timezone

import httpx
from sqlalchemy.orm import Session as DbSession

from app.modules.audit.service import audit
from app.modules.secrets.store import SecretStore, SecretNotFoundError, SecretRevokedError

logger = logging.getLogger(__name__)
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


def _get_service_token(token_ref: str, secret_store: SecretStore) -> tuple[str, str]:
    """Récupère les credentials CF Access depuis le SecretStore chiffré.

    Retourne ("", "") si le token est absent, révoqué ou illisible.
    Ne lève jamais d'exception — un token manquant doit résulter en un rejet CF, pas un crash.
    """
    try:
        payload = json.loads(secret_store.get(token_ref))
        return payload.get("client_id", ""), payload.get("client_secret", "")
    except (SecretNotFoundError, SecretRevokedError):
        return "", ""
    except Exception:
        logger.warning("Erreur inattendue lors de la lecture du service token %s", token_ref, exc_info=True)
        return "", ""


def get_upstream_proxy_headers(
    env: Environment,
    user_id: str,
    request_headers: dict,
    secret_store: SecretStore | None = None,
) -> dict:
    """Construit les headers à envoyer à l'upstream.

    - Retire les headers de session et de transport
    - Empêche le spoofing de X-DevGate-User côté client
    - Injecte les credentials CF Access via SecretStore si service_token_ref configuré
    """
    proxy_headers = {
        k: v for k, v in request_headers.items()
        if k.lower() not in ("host", "cookie", "accept-encoding", "x-devgate-user")
    }
    proxy_headers["Accept-Encoding"] = "identity"
    proxy_headers["X-DevGate-User"] = user_id

    if env.service_token_ref and secret_store is not None:
        cf_client_id, cf_client_secret = _get_service_token(env.service_token_ref, secret_store)
        if cf_client_id:
            proxy_headers["CF-Access-Client-Id"] = cf_client_id
        if cf_client_secret:
            proxy_headers["CF-Access-Client-Secret"] = cf_client_secret

    return proxy_headers


async def proxy_request(
    env: Environment,
    method: str,
    path: str,
    headers: dict,
    body: bytes | None,
    user: User,
    db: DbSession,
    secret_store: SecretStore | None = None,
) -> httpx.Response:
    """Proxifie la requête vers l'upstream Cloudflare protégé."""
    if not env.upstream_hostname:
        raise UpstreamUnavailableException("Upstream non configuré")

    upstream_url = f"https://{env.upstream_hostname}{path}"

    proxy_headers = get_upstream_proxy_headers(env, user.id, headers, secret_store)

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            response = await client.request(
                method=method,
                url=upstream_url,
                headers=proxy_headers,
                content=body,
            )
    except httpx.ConnectError as e:
        audit(
            db,
            actor_user_id=user.id,
            event_type="gateway.request.failed",
            target_type="environment",
            target_id=env.id,
            metadata={"reason": "upstream_unavailable", "detail": str(e)[:200]},
        )
        db.commit()
        raise UpstreamUnavailableException(f"Impossible de joindre l'upstream : {e}") from e
    except httpx.TimeoutException as e:
        audit(
            db,
            actor_user_id=user.id,
            event_type="gateway.request.failed",
            target_type="environment",
            target_id=env.id,
            metadata={"reason": "timeout"},
        )
        db.commit()
        raise UpstreamUnavailableException("L'upstream n'a pas répondu à temps") from e

    latency_ms = int((time.monotonic() - start) * 1000)

    audit(
        db,
        actor_user_id=user.id,
        event_type="gateway.resource.accessed",
        target_type="environment",
        target_id=env.id,
        metadata={
            "status_code": response.status_code,
            "path": path,
            "latency_ms": latency_ms,
            "is_5xx": response.status_code >= 500,
            "is_cf_refused": response.status_code == 403,
        },
    )
    db.commit()

    return response
