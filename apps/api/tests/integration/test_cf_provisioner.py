"""Tests d'intégration — provisioner saga Cloudflare (ADR-001)."""
import base64

import pytest

from app.modules.cloudflare.fake_client import FakeCFClient, FakeCFError
from app.modules.cloudflare.provisioner import (
    ProvisioningError,
    compensate_provisioning_job,
    run_provisioning_job,
)
from app.modules.secrets.store import EncryptedDatabaseSecretStore
from app.shared.models import Environment, Organization, Project, ProvisioningJob

TEST_MASTER_KEY = base64.b64encode(b"a" * 32).decode()


def _make_env(db_session) -> Environment:
    org = Organization(id="org-prov", name="Prov", slug="prov-org")
    proj = Project(id="proj-prov", organization_id="org-prov", name="P", slug="p")
    env = Environment(
        id="env-prov",
        project_id="proj-prov",
        name="E",
        slug="e-prov",
        kind="staging",
        public_hostname="e.prov.example.com",
        cloudflare_tunnel_id="tunnel-prov-1",
        status="pending",
    )
    db_session.add_all([org, proj, env])
    db_session.commit()
    return env


def _make_job(db_session, env: Environment) -> ProvisioningJob:
    job = ProvisioningJob(environment_id=env.id, state="pending")
    db_session.add(job)
    db_session.commit()
    return job


def _secret_store(db_session):
    return EncryptedDatabaseSecretStore(master_key_b64=TEST_MASTER_KEY, db=db_session)


def test_provisioner_happy_path(db_session):
    """Chemin nominal : pending → active, DNS en dernier."""
    env = _make_env(db_session)
    job = _make_job(db_session, env)
    fake_cf = FakeCFClient()
    store = _secret_store(db_session)

    final_state = run_provisioning_job(job, env, fake_cf, store, db_session)

    assert final_state == "active"
    assert len(fake_cf.created_apps) == 1
    assert len(fake_cf.created_policies) == 1
    assert len(fake_cf.created_tokens) == 1
    assert len(fake_cf.created_dns) == 1

    db_session.refresh(job)
    db_session.refresh(env)
    assert job.secret_persisted is True
    assert job.dns_published is True
    assert env.service_token_ref is not None
    assert env.service_token_ref.startswith("sec_")
    assert env.status == "active"


def test_provisioner_dns_requires_secret_persisted(db_session):
    """Le DNS ne doit jamais être publié si secret_persisted=False (ADR-001 R2)."""
    env = _make_env(db_session)
    job = _make_job(db_session, env)
    # Forcer un état post-token mais secret pas encore persisté
    job.state = "secret_persisted"
    job.secret_persisted = False  # Incohérence volontaire
    job.cloudflare_access_app_id = "app-x"
    job.cloudflare_policy_id = "policy-x"
    job.cloudflare_service_token_id = "token-x"
    db_session.commit()

    fake_cf = FakeCFClient()
    store = _secret_store(db_session)

    with pytest.raises(ProvisioningError):
        run_provisioning_job(job, env, fake_cf, store, db_session)

    db_session.refresh(job)
    assert job.state == "failed_recoverable"
    # DNS non publié
    assert len(fake_cf.created_dns) == 0


def test_provisioner_failure_sets_failed_recoverable(db_session):
    """Une erreur CF → state=failed_recoverable, last_error renseigné."""
    env = _make_env(db_session)
    job = _make_job(db_session, env)
    fake_cf = FakeCFClient()
    fake_cf.fail_at = "create_access_app"
    store = _secret_store(db_session)

    with pytest.raises(ProvisioningError):
        run_provisioning_job(job, env, fake_cf, store, db_session)

    db_session.refresh(job)
    assert job.state == "failed_recoverable"
    assert job.last_error is not None


def test_provisioner_persists_after_each_cf_call(db_session):
    """Après create_access_app, cloudflare_access_app_id est en base avant la suite."""
    env = _make_env(db_session)
    job = _make_job(db_session, env)
    fake_cf = FakeCFClient()
    fake_cf.fail_at = "create_policy"  # Crash après création de l'app
    store = _secret_store(db_session)

    with pytest.raises(ProvisioningError):
        run_provisioning_job(job, env, fake_cf, store, db_session)

    # L'app CF est persistée malgré le crash
    db_session.refresh(job)
    assert job.cloudflare_access_app_id is not None
    assert job.cloudflare_access_app_id.startswith("app-fake-")


def test_compensate_removes_cf_resources(db_session):
    """compensate() supprime les ressources CF dans l'ordre inverse."""
    env = _make_env(db_session)
    job = _make_job(db_session, env)
    fake_cf = FakeCFClient()
    # Simuler un job partiellement créé
    job.state = "failed_recoverable"
    job.cloudflare_access_app_id = "app-to-delete"
    job.cloudflare_policy_id = "policy-to-delete"
    job.cloudflare_service_token_id = "token-to-revoke"
    job.dns_record_id = "dns-to-delete"
    db_session.commit()

    final_state = compensate_provisioning_job(job, fake_cf, db_session)

    assert final_state == "rolled_back"
    assert "dns-to-delete" in fake_cf.deleted_dns
    assert "token-to-revoke" in fake_cf.revoked_tokens
    assert "app-to-delete" in fake_cf.deleted_apps
