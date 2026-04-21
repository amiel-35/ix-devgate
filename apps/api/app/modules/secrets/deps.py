"""Dépendance FastAPI pour obtenir le SecretStore configuré."""
from app.config import settings
from app.modules.secrets.store import EncryptedDatabaseSecretStore, SecretStore


def get_secret_store(db) -> SecretStore:
    """Retourne un EncryptedDatabaseSecretStore configuré depuis DEVGATE_MASTER_KEY.

    Lève RuntimeError si la clé est absente.
    Ne doit jamais être appelé depuis le frontend ou les logs.
    """
    master_key = settings.DEVGATE_MASTER_KEY
    if not master_key:
        raise RuntimeError(
            "DEVGATE_MASTER_KEY non configurée — impossible d'accéder au secret store"
        )
    return EncryptedDatabaseSecretStore(master_key_b64=master_key, db=db)
