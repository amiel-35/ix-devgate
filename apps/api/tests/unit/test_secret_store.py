"""Tests unitaires — secret store."""
import pytest

from app.shared.models import EncryptedSecret
from app.modules.secrets.store import FakeSecretStore, SecretNotFoundError, SecretRevokedError


def test_encrypted_secret_model_exists():
    cols = {c.name for c in EncryptedSecret.__table__.columns}
    assert "secret_ref" in cols
    assert "ciphertext" in cols
    assert "nonce" in cols
    assert "key_id" in cols
    assert "revoked_at" in cols


def test_fake_store_put_returns_ref():
    store = FakeSecretStore()
    ref = store.put("test_type", "my-secret")
    assert ref.startswith("sec_")


def test_fake_store_get_returns_plaintext():
    store = FakeSecretStore()
    ref = store.put("test_type", "my-secret")
    assert store.get(ref) == "my-secret"


def test_fake_store_get_unknown_raises():
    store = FakeSecretStore()
    with pytest.raises(SecretNotFoundError):
        store.get("sec_unknown")


def test_fake_store_revoke_then_get_raises():
    store = FakeSecretStore()
    ref = store.put("test_type", "my-secret")
    store.revoke(ref)
    with pytest.raises(SecretRevokedError):
        store.get(ref)


def test_fake_store_revoke_unknown_raises():
    store = FakeSecretStore()
    with pytest.raises(SecretNotFoundError):
        store.revoke("sec_unknown")


def test_fake_store_multiple_secrets_isolated():
    store = FakeSecretStore()
    ref1 = store.put("type_a", "secret-a")
    ref2 = store.put("type_b", "secret-b")
    assert store.get(ref1) == "secret-a"
    assert store.get(ref2) == "secret-b"
