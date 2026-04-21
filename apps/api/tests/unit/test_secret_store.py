"""Tests unitaires — secret store."""
from app.shared.models import EncryptedSecret


def test_encrypted_secret_model_exists():
    """Le modèle EncryptedSecret est importable et a les colonnes attendues."""
    cols = {c.name for c in EncryptedSecret.__table__.columns}
    assert "secret_ref" in cols
    assert "ciphertext" in cols
    assert "nonce" in cols
    assert "key_id" in cols
    assert "revoked_at" in cols
