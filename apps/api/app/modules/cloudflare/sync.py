"""
Sync job Cloudflare — maintient l'inventaire DiscoveredTunnel.

Règles :
- Ne crée jamais d'Environment automatiquement (ADR-001 §1).
- Seuls les tunnels préfixés 'devgate-' sont importés.
- Un tunnel absent du sync passe en 'orphaned' seulement s'il était 'discovered'.
- Les tunnels 'assigned' et 'active' ne sont pas orphelinés automatiquement.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DbSession

from app.modules.cloudflare.client import CFClient
from app.shared.models import DiscoveredTunnel

logger = logging.getLogger(__name__)


def sync_tunnels(db: DbSession, cf) -> dict:
    """
    Interroge l'API CF, upsert les DiscoveredTunnel.
    Retourne {"discovered": N, "updated": N, "orphaned": N} ou {"error": "..."}.
    """
    try:
        tunnels = cf.list_tunnels()
    except Exception as e:
        logger.warning("CF sync failed: %s", e, exc_info=True)
        return {"error": str(e), "discovered": 0, "updated": 0, "orphaned": 0}

    now = datetime.now(tz=timezone.utc)
    seen_ids: set[str] = set()
    discovered_count = 0
    updated_count = 0

    for t in tunnels:
        seen_ids.add(t.id)
        existing = (
            db.query(DiscoveredTunnel)
            .filter(DiscoveredTunnel.cloudflare_tunnel_id == t.id)
            .first()
        )
        if existing:
            existing.last_seen_at = now
            existing.metadata_json = {
                "cf_status": t.status,
                "connections": t.connections,
            }
            updated_count += 1
        else:
            db.add(DiscoveredTunnel(
                cloudflare_tunnel_id=t.id,
                name=t.name,
                status="discovered",
                last_seen_at=now,
                metadata_json={"cf_status": t.status, "connections": t.connections},
            ))
            discovered_count += 1

    # Orphelins : tunnels 'discovered' non vus dans ce cycle
    orphaned_count = 0
    discovered_in_db = (
        db.query(DiscoveredTunnel)
        .filter(DiscoveredTunnel.status == "discovered")
        .all()
    )
    for dt in discovered_in_db:
        if dt.cloudflare_tunnel_id not in seen_ids:
            dt.status = "orphaned"
            orphaned_count += 1
            logger.info("Tunnel orphelin détecté : %s (%s)", dt.name, dt.cloudflare_tunnel_id)

    db.commit()
    return {"discovered": discovered_count, "updated": updated_count, "orphaned": orphaned_count}
