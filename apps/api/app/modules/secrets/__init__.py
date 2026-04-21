"""Module secret store — chiffrement AES-256-GCM des secrets serveur.
Voir ADR-002 pour la doctrine et les règles d'usage.
"""
from app.modules.secrets.store import (
    EncryptedDatabaseSecretStore,
    FakeSecretStore,
    SecretNotFoundError,
    SecretRevokedError,
    SecretStore,
)

__all__ = [
    "SecretStore",
    "FakeSecretStore",
    "EncryptedDatabaseSecretStore",
    "SecretNotFoundError",
    "SecretRevokedError",
]
