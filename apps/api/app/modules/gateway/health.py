"""
Health check service — sonde les upstreams et écrit les snapshots.
Règle : jamais de credential Cloudflare dans les logs ou les réponses admin.
"""
import asyncio
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session as DbSession

from app.shared.models import Environment, TunnelHealthSnapshot


async def check_environment_health(env: Environment, db: DbSession) -> TunnelHealthSnapshot:
    """Effectue un HEAD HTTP vers upstream_hostname et écrit un TunnelHealthSnapshot.

    Retourne le snapshot créé.
    Status possibles : "online" | "offline" | "unknown"
    """
    if not env.upstream_hostname:
        snapshot = TunnelHealthSnapshot(
            environment_id=env.id,
            status="unknown",
            replica_count=0,
            observed_at=datetime.now(tz=timezone.utc),
            metadata_json={"reason": "upstream_hostname non configuré"},
        )
        db.add(snapshot)
        db.commit()
        return snapshot

    status = "offline"
    latency_ms: int | None = None
    meta: dict = {}

    try:
        start = asyncio.get_event_loop().time()
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.head(f"https://{env.upstream_hostname}/")
        latency_ms = int((asyncio.get_event_loop().time() - start) * 1000)
        # 200–499 = online (même un 403 signifie que le serveur répond)
        if response.status_code < 500:
            status = "online"
        else:
            status = "offline"
        meta = {"status_code": response.status_code, "latency_ms": latency_ms}
    except httpx.ConnectError as e:
        status = "offline"
        meta = {"error": "connect_error", "detail": str(e)[:200]}
    except httpx.TimeoutException:
        status = "offline"
        meta = {"error": "timeout"}
    except Exception as e:
        status = "unknown"
        meta = {"error": "unexpected", "detail": str(e)[:200]}

    snapshot = TunnelHealthSnapshot(
        environment_id=env.id,
        status=status,
        replica_count=0,
        observed_at=datetime.now(tz=timezone.utc),
        metadata_json=meta,
    )
    db.add(snapshot)
    db.commit()
    return snapshot
