"""
Secret store — interface + implémentations.

FakeSecretStore     : en mémoire, sans chiffrement, pour les tests unitaires.
EncryptedDatabaseSecretStore : AES-256-GCM + HKDF, pour la production.

Règles (ADR-002) :
- put() fait flush() mais PAS commit() — le code appelant owns la transaction.
- Le secret_ref est généré avant le chiffrement et sert d'AAD.
- Le couple (nonce, key) ne doit jamais être réutilisé.
- DNS ne doit être publié qu'après secret_persisted = True.
"""
import base64
import json
import logging
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SecretNotFoundError(Exception):
    """Secret absent ou inconnu."""


class SecretRevokedError(Exception):
    """Secret révoqué — inutilisable."""


class SecretStore(ABC):

    @abstractmethod
    def put(
        self,
        secret_type: str,
        plaintext: str,
        owner_type: str | None = None,
        owner_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Chiffre et stocke le secret. Retourne un secret_ref opaque (sec_<uuid>)."""

    @abstractmethod
    def get(self, secret_ref: str) -> str:
        """Retourne le plaintext. Lève SecretNotFoundError ou SecretRevokedError."""

    @abstractmethod
    def revoke(self, secret_ref: str) -> None:
        """Marque le secret comme révoqué. Lève SecretNotFoundError si absent."""


# ── FakeSecretStore ───────────────────────────────────────────────

class FakeSecretStore(SecretStore):
    """Store en mémoire sans chiffrement — uniquement pour les tests unitaires."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._revoked: set[str] = set()

    def put(
        self,
        secret_type: str,
        plaintext: str,
        owner_type: str | None = None,
        owner_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        ref = f"sec_{uuid.uuid4().hex}"
        self._store[ref] = plaintext
        return ref

    def get(self, secret_ref: str) -> str:
        if secret_ref in self._revoked:
            raise SecretRevokedError(secret_ref)
        if secret_ref not in self._store:
            raise SecretNotFoundError(secret_ref)
        return self._store[secret_ref]

    def revoke(self, secret_ref: str) -> None:
        if secret_ref not in self._store:
            raise SecretNotFoundError(secret_ref)
        self._revoked.add(secret_ref)


# ── EncryptedDatabaseSecretStore ──────────────────────────────────

class EncryptedDatabaseSecretStore(SecretStore):
    """Store chiffré AES-256-GCM avec HKDF-SHA256 — pour la production et les tests d'intégration.

    master_key_b64 : DEVGATE_MASTER_KEY en base64 (32 bytes).
    db             : session SQLAlchemy — le store fait flush() mais pas commit().
    """

    def __init__(self, master_key_b64: str, db) -> None:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF

        master_key = base64.b64decode(master_key_b64, validate=True)
        if len(master_key) != 32:
            raise ValueError(
                f"DEVGATE_MASTER_KEY doit décoder en 32 bytes — obtenu {len(master_key)} bytes"
            )
        self._aes_key: bytes = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,  # RFC 5869 §2.2 : salt=None équivaut à zéros de taille HashLen.
                        # Dérivation déterministe : même DEVGATE_MASTER_KEY → même clé AES.
                        # CONTRAINTE : rotation de DEVGATE_MASTER_KEY = re-chiffrement complet en base.
            info=b"devgate-secret-store-v1",
        ).derive(master_key)
        self._db = db

    def _make_aad(
        self,
        secret_ref: str,
        secret_type: str,
        owner_type: str | None,
        owner_id: str | None,
        key_id: str,
    ) -> bytes:
        """AAD déterministe — lie le ciphertext à son contexte métier."""
        return json.dumps(
            {
                "secret_ref": secret_ref,
                "secret_type": secret_type,
                "owner_type": owner_type,
                "owner_id": owner_id,
                "key_id": key_id,
            },
            sort_keys=True,
        ).encode()

    def put(
        self,
        secret_type: str,
        plaintext: str,
        owner_type: str | None = None,
        owner_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from app.shared.models import EncryptedSecret

        # 1. Générer la ref AVANT de chiffrer — elle sert d'AAD
        secret_ref = f"sec_{uuid.uuid4().hex}"
        key_id = "v1"

        nonce = os.urandom(12)  # 96 bits, jamais réutilisé
        aad = self._make_aad(secret_ref, secret_type, owner_type, owner_id, key_id)

        aesgcm = AESGCM(self._aes_key)
        # ciphertext inclut le tag GCM en suffixe (comportement natif de cryptography)
        ciphertext_bytes = aesgcm.encrypt(nonce, plaintext.encode(), aad)

        record = EncryptedSecret(
            secret_ref=secret_ref,
            secret_type=secret_type,
            owner_type=owner_type,
            owner_id=owner_id,
            key_id=key_id,
            ciphertext=base64.b64encode(ciphertext_bytes).decode(),
            nonce=base64.b64encode(nonce).decode(),
            algorithm="AES-256-GCM",
            metadata_json=metadata,
        )
        self._db.add(record)
        self._db.flush()  # persist sans commit — le code appelant owns la transaction
        return secret_ref

    def get(self, secret_ref: str) -> str:
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from app.shared.models import EncryptedSecret

        record = (
            self._db.query(EncryptedSecret)
            .filter(EncryptedSecret.secret_ref == secret_ref)
            .first()
        )
        if not record:
            raise SecretNotFoundError(secret_ref)
        if record.revoked_at is not None:
            raise SecretRevokedError(secret_ref)

        aad = self._make_aad(
            record.secret_ref,
            record.secret_type,
            record.owner_type,
            record.owner_id,
            record.key_id,
        )
        nonce = base64.b64decode(record.nonce)
        ciphertext = base64.b64decode(record.ciphertext)

        aesgcm = AESGCM(self._aes_key)
        try:
            plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, aad)
        except InvalidTag as e:
            # Événement de sécurité : tag invalide peut indiquer une altération ou une mauvaise clé.
            # On ne distingue pas cela d'un "non trouvé" à l'extérieur pour éviter les oracles,
            # mais on log en WARNING pour que les opérateurs puissent détecter un problème.
            logger.warning("Déchiffrement GCM échoué pour un secret existant en base", exc_info=False)
            raise SecretNotFoundError("Déchiffrement impossible") from e

        return plaintext_bytes.decode()

    def revoke(self, secret_ref: str) -> None:
        from app.shared.models import EncryptedSecret

        record = (
            self._db.query(EncryptedSecret)
            .filter(EncryptedSecret.secret_ref == secret_ref)
            .first()
        )
        if not record:
            raise SecretNotFoundError(secret_ref)
        record.revoked_at = datetime.now(tz=timezone.utc)
        self._db.flush()
