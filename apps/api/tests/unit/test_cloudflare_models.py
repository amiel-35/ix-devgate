"""Tests unitaires — modèles Cloudflare."""
from app.shared.models import DiscoveredTunnel, ProvisioningJob, Environment


def test_discovered_tunnel_model_exists():
    cols = {c.name for c in DiscoveredTunnel.__table__.columns}
    assert "cloudflare_tunnel_id" in cols
    assert "status" in cols
    assert "last_seen_at" in cols


def test_provisioning_job_model_exists():
    cols = {c.name for c in ProvisioningJob.__table__.columns}
    assert "state" in cols
    assert "secret_persisted" in cols
    assert "dns_published" in cols
    assert "cloudflare_access_app_id" in cols
    assert "cloudflare_service_token_id" in cols


def test_environment_has_cf_columns():
    cols = {c.name for c in Environment.__table__.columns}
    assert "discovered_tunnel_id" in cols
    assert "provisioning_status" in cols
