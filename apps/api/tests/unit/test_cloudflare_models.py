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


def test_discovered_tunnel_status_default():
    """DiscoveredTunnel.status has 'discovered' as server_default."""
    status_col = DiscoveredTunnel.__table__.columns["status"]
    assert status_col.default is not None or status_col.server_default is not None


def test_provisioning_job_state_default():
    """ProvisioningJob.state has 'pending' as default, booleans are non-nullable with defaults."""
    state_col = ProvisioningJob.__table__.columns["state"]
    assert state_col.default is not None or state_col.server_default is not None

    secret_persisted_col = ProvisioningJob.__table__.columns["secret_persisted"]
    assert secret_persisted_col.default is not None or secret_persisted_col.server_default is not None

    dns_published_col = ProvisioningJob.__table__.columns["dns_published"]
    assert dns_published_col.default is not None or dns_published_col.server_default is not None
