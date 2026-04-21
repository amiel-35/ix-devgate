"""Tests d'intégration — sync tunnels CF."""
from datetime import datetime, timezone

from app.modules.cloudflare.client import CFTunnel
from app.modules.cloudflare.fake_client import FakeCFClient
from app.modules.cloudflare.sync import sync_tunnels
from app.shared.models import DiscoveredTunnel


def _fake_cf_with_tunnels(*tunnels: CFTunnel) -> FakeCFClient:
    fake = FakeCFClient()
    fake.tunnels = list(tunnels)
    return fake


def test_sync_creates_new_discovered_tunnel(db_session):
    """Un nouveau tunnel CF est créé comme DiscoveredTunnel."""
    fake = _fake_cf_with_tunnels(
        CFTunnel(id="t-1", name="devgate-acme", status="active"),
    )
    result = sync_tunnels(db_session, fake)

    assert result["discovered"] == 1
    assert result["updated"] == 0

    dt = db_session.query(DiscoveredTunnel).filter(
        DiscoveredTunnel.cloudflare_tunnel_id == "t-1"
    ).first()
    assert dt is not None
    assert dt.name == "devgate-acme"
    assert dt.status == "discovered"


def test_sync_updates_existing_tunnel(db_session):
    """Un tunnel déjà connu est mis à jour (last_seen_at)."""
    existing = DiscoveredTunnel(
        cloudflare_tunnel_id="t-1",
        name="devgate-acme",
        status="discovered",
    )
    db_session.add(existing)
    db_session.commit()

    fake = _fake_cf_with_tunnels(
        CFTunnel(id="t-1", name="devgate-acme", status="active"),
    )
    result = sync_tunnels(db_session, fake)

    assert result["updated"] == 1
    assert result["discovered"] == 0

    db_session.refresh(existing)
    assert existing.last_seen_at is not None


def test_sync_marks_absent_tunnel_as_orphaned(db_session):
    """Un tunnel en base mais absent du sync CF devient orphaned."""
    existing = DiscoveredTunnel(
        cloudflare_tunnel_id="t-ghost",
        name="devgate-ghost",
        status="discovered",
    )
    db_session.add(existing)
    db_session.commit()

    fake = _fake_cf_with_tunnels(
        CFTunnel(id="t-other", name="devgate-other", status="active"),
    )
    result = sync_tunnels(db_session, fake)

    assert result["orphaned"] == 1
    db_session.refresh(existing)
    assert existing.status == "orphaned"


def test_sync_does_not_orphan_assigned_tunnel(db_session):
    """Un tunnel assigné n'est pas marqué orphelin même s'il disparaît du sync."""
    assigned = DiscoveredTunnel(
        cloudflare_tunnel_id="t-assigned",
        name="devgate-assigned",
        status="assigned",
    )
    db_session.add(assigned)
    db_session.commit()

    fake = FakeCFClient()
    fake.tunnels = []  # CF retourne aucun tunnel
    result = sync_tunnels(db_session, fake)

    db_session.refresh(assigned)
    assert assigned.status == "assigned"  # inchangé
    assert result["orphaned"] == 0


def test_sync_handles_cf_error_gracefully(db_session):
    """En cas d'erreur CF API, sync retourne une erreur sans crash."""
    fake = FakeCFClient()
    fake.fail_at = "list_tunnels"

    result = sync_tunnels(db_session, fake)
    assert "error" in result
