"""
Gateway router — point d'entrée pour le trafic proxifié.
L'URL publique est /gateway/{env_id}/{path:path}
Le navigateur ne voit jamais l'upstream Cloudflare.
"""
import asyncio

import websockets
import websockets.exceptions
from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.modules.gateway.service import proxy_request, resolve_environment
from app.shared.deps import get_current_user
from app.shared.models import Session as SessionModel, User

router = APIRouter()

# Headers de transport à ne pas retransmettre au navigateur
_EXCLUDED_RESPONSE_HEADERS = frozenset({
    "transfer-encoding",
    "content-length",   # recalculé par starlette
})


@router.api_route(
    "/{env_id}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
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

    # Construire la réponse en préservant les headers multi-valeurs (Set-Cookie, etc.)
    response = Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        media_type=upstream_response.headers.get("content-type"),
    )
    for key, value in upstream_response.headers.multi_items():
        if key.lower() not in _EXCLUDED_RESPONSE_HEADERS:
            response.headers.append(key, value)

    return response


@router.websocket("/{env_id}/{path:path}")
async def gateway_ws_proxy(
    env_id: str,
    path: str,
    websocket: WebSocket,
    db: DbSession = Depends(get_db),
):
    """Proxy WebSocket bidirectionnel vers l'upstream."""
    from datetime import datetime, timezone

    session_id = websocket.cookies.get("devgate_session")
    if not session_id:
        await websocket.close(code=1008)  # Policy Violation
        return

    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        await websocket.close(code=1008)
        return

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(tz=timezone.utc):
        await websocket.close(code=1008)
        return

    user = db.query(User).filter(User.id == session.user_id).first()
    if not user:
        await websocket.close(code=1008)
        return

    try:
        env = resolve_environment(env_id, user, db)
    except Exception:
        await websocket.close(code=1008)
        return

    if not env.upstream_hostname:
        await websocket.close(code=1011)  # Internal Error
        return

    upstream_ws_url = f"wss://{env.upstream_hostname}/{path}"

    await websocket.accept()

    try:
        async with websockets.connect(upstream_ws_url) as upstream_ws:

            async def client_to_upstream() -> None:
                try:
                    async for message in websocket.iter_bytes():
                        await upstream_ws.send(message)
                except WebSocketDisconnect:
                    pass

            async def upstream_to_client() -> None:
                try:
                    async for message in upstream_ws:
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)
                except websockets.exceptions.ConnectionClosed:
                    pass

            await asyncio.gather(
                client_to_upstream(),
                upstream_to_client(),
                return_exceptions=True,
            )

    except websockets.exceptions.WebSocketException:
        pass
    except Exception:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
