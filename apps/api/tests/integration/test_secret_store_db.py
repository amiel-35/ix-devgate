"""Tests d'intégration — EncryptedDatabaseSecretStore avec SQLite."""
import base64
import json

import pytest

from app.modules.secrets.store import (
    EncryptedDatabaseSecretStore,
    SecretNotFoundError,
    SecretRevokedError,
)

# Clé de test fixe et déterministe (32 bytes en base64)
TEST_MASTER_KEY = base64.b64encode(b"devgate-test-key-32bytes-padding!").decode()


def _store(db_session) -> EncryptedDatabaseSecretStore:
    return EncryptedDatabaseSecretStore(master_key_b64=TEST_MASTER_KEY, db=db_session)


def test_put_and_get_roundtrip(db_session):
    """put() + get() retourne le plaintext original."""
    store = _store(db_session)
    ref = store.put("cf_service_token", "my-secret-payload")
    db_session.commit()

    assert store.get(ref) == "my-secret-payload"


def test_ref_has_sec_prefix(db_session):
    """Le secret_ref commence par 'sec_'."""
    store = _store(db_session)
    ref = store.put("test_type", "data")
    db_session.commit()
    assert ref.startswith("sec_")


def test_two_puts_have_different_refs(db_session):
    """Chaque put() génère un ref unique."""
    store = _store(db_session)
    ref1 = store.put("test_type", "data")
    ref2 = store.put("test_type", "data")
    db_session.commit()
    assert ref1 != ref2


def test_get_unknown_raises(db_session):
    """get() sur un ref inconnu lève SecretNotFoundError."""
    store = _store(db_session)
    with pytest.raises(SecretNotFoundError):
        store.get("sec_unknown123")


def test_revoke_then_get_raises(db_session):
    """Après revoke(), get() lève SecretRevokedError."""
    store = _store(db_session)
    ref = store.put("cf_service_token", "to-revoke")
    db_session.commit()

    store.revoke(ref)
    db_session.commit()

    with pytest.raises(SecretRevokedError):
        store.get(ref)


def test_wrong_key_cannot_decrypt(db_session):
    """Un store avec une clé différente ne peut pas déchiffrer."""
    store = _store(db_session)
    ref = store.put("test_type", "sensitive")
    db_session.commit()

    wrong_key = base64.b64encode(b"completely-different-key-32bytes").decode()
    store_wrong = EncryptedDatabaseSecretStore(master_key_b64=wrong_key, db=db_session)

    with pytest.raises(SecretNotFoundError):
        store_wrong.get(ref)


def test_json_payload_roundtrip(db_session):
    """Un payload JSON (service token CF) survit au chiffrement/déchiffrement."""
    store = _store(db_session)
    payload = json.dumps({"client_id": "id-abc", "client_secret": "secret-xyz"})
    ref = store.put(
        "cloudflare_service_token",
        payload,
        owner_type="environment",
        owner_id="env-test",
    )
    db_session.commit()

    recovered = json.loads(store.get(ref))
    assert recovered["client_id"] == "id-abc"
    assert recovered["client_secret"] == "secret-xyz"


def test_owner_metadata_stored(db_session):
    """owner_type et owner_id sont persistés."""
    from app.shared.models import EncryptedSecret

    store = _store(db_session)
    ref = store.put("test", "data", owner_type="environment", owner_id="env-42")
    db_session.commit()

    record = db_session.query(EncryptedSecret).filter(
        EncryptedSecret.secret_ref == ref
    ).first()
    assert record.owner_type == "environment"
    assert record.owner_id == "env-42"
