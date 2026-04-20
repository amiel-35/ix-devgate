"""
Gateway router — point d'entrée pour le trafic proxifié.
L'URL publique est /gateway/{env_id}/{path:path}
Le navigateur ne voit jamais l'upstream Cloudflare.
"""
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.modules.gateway.service import proxy_request, resolve_environment
from app.shared.deps import get_current_user
from app.shared.models import User

router = APIRouter()


@router.api_route("/{env_id}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def gateway_proxy(
    env_id: str,
    path: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    env = resolve_environment(env_id, user, db)

    body = await request.body()
    upstream_response = await proxy_request(
        env=env,
        method=request.method,
        path=f"/{path}",
        headers=dict(request.headers),
        body=body or None,
        user=user,
        db=db,
    )

    # Filtrer les headers de réponse sensibles
    excluded = {"transfer-encoding", "content-encoding"}
    response_headers = {
        k: v for k, v in upstream_response.headers.items()
        if k.lower() not in excluded
    }

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=response_headers,
        media_type=upstream_response.headers.get("content-type"),
    )
