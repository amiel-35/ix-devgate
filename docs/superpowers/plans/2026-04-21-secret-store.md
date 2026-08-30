# Secret Store interne chiffré — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implémenter le secret store chiffré AES-256-GCM (ADR-002) et brancher le gateway dessus pour que les service tokens Cloudflare Access soient stockés en base chiffrée plutôt qu'en variables d'environnement.

**Architecture:** Un module `secrets` expose une interface `SecretStore` avec deux implémentations : `FakeSecretStore` (mémoire, pour tests) et `EncryptedDatabaseSecretStore` (AES-256-GCM + HKDF, pour prod). Le gateway appelle `SecretStore.get(service_token_ref)` pour récupérer les credentials CF. Un endpoint admin `PUT /admin/environments/{id}/service-token` permet de stocker un token via le back-office.

**Tech Stack:** Python `cryptography` (HKDF-SHA256 + AESGCM), SQLAlchemy, FastAPI, pytest.

**Aucune clé API Cloudflare requise** — cette phase est entièrement backend Python.

---

## Fichiers créés ou modifiés

| Fichier | Action | Responsabilité |
|---|---|---|
| `apps/api/requirements.txt` | Modify | Ajouter `cryptography>=42` |
| `apps/api/app/shared/models.py` | Modify | Ajouter `EncryptedSecret` |
| `apps/api/app/modules/secrets/__init__.py` | Create | Exports publics |
| `apps/api/app/modules/secrets/store.py` | Create | `SecretStore` ABC + `FakeSecretStore` + `EncryptedDatabaseSecretStore` + exceptions |
| `apps/api/app/modules/secrets/deps.py` | Create | `get_secret_store(db)` — lit `DEVGATE_MASTER_KEY` |
| `apps/api/app/modules/admin/schemas.py` | Modify | Ajouter `StoreServiceTokenRequest` |
| `apps/api/app/modules/admin/router.py` | Modify | Ajouter `PUT /environments/{env_id}/service-token` |
| `apps/api/app/modules/gateway/service.py` | Modify | Utiliser `SecretStore` au lieu de `os.environ` |
| `apps/api/app/modules/gateway/router.py` | Modify | Créer et passer `secret_store` aux fonctions proxy |
| `apps/api/tests/unit/test_secret_store.py` | Create | Tests unitaires `FakeSecretStore` |
| `apps/api/tests/integration/test_secret_store_db.py` | Create | Tests intégration `EncryptedDatabaseSecretStore` |
| `apps/api/tests/integration/test_gateway.py` | Modify | Mise à jour `test_gateway_injects_cf_service_token` |

---

## Task 1: Dépendance cryptography + modèle EncryptedSecret

**Files:**
- Modify: `apps/api/requirements.txt`
- Modify: `apps/api/app/shared/models.py`

- [ ] **Step 1 : Écrire le test qui vérifie que le modèle crée sa table**

Dans `apps/api/tests/unit/test_secret_store.py`, créer le fichier avec ce contenu minimal :

```python
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
```

- [ ] **Step 2 : Vérifier que le test échoue**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/unit/test_secret_store.py -v
```

Expected: `FAILED` — `ImportError: cannot import name 'EncryptedSecret'`

- [ ] **Step 3 : Ajouter `cryptography` à requirements.txt**

Dans `apps/api/requirements.txt`, ajouter après `httpx>=0.28` :

```
cryptography>=42
```

- [ ] **Step 4 : Installer la dépendance**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pip install "cryptography>=42"
```

Expected: `Successfully installed cryptography-XX.X.X`

- [ ] **Step 5 : Ajouter le modèle `EncryptedSecret` à `shared/models.py`**

À la fin de `apps/api/app/shared/models.py`, ajouter :

```python
# ── EncryptedSecret ───────────────────────────────────────────────

class EncryptedSecret(Base):
    __tablename__ = "encrypted_secrets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    secret_ref: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    secret_type: Mapped[str] = mapped_column(String, nullable=False)
    owner_type: Mapped[str | None] = mapped_column(String)
    owner_id: Mapped[str | None] = mapped_column(String)
    key_id: Mapped[str] = mapped_column(String, nullable=False, default="v1")
    # ciphertext contient le tag GCM en suffixe (format natif cryptography.AESGCM)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)   # base64
    nonce: Mapped[str] = mapped_column(String, nullable=False)       # base64, 12 bytes
    algorithm: Mapped[str] = mapped_column(String, nullable=False, default="AES-256-GCM")
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 6 : Vérifier que le test passe**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/unit/test_secret_store.py -v
```

Expected: `PASSED`

- [ ] **Step 7 : Vérifier la suite complète (pas de régression)**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/ -q
```

Expected: 74+ tests passent.

- [ ] **Step 8 : Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/api/requirements.txt apps/api/app/shared/models.py apps/api/tests/unit/test_secret_store.py
git commit -m "feat(secrets): modèle EncryptedSecret + dépendance cryptography"
```

---

## Task 2: Interface SecretStore + FakeSecretStore

**Files:**
- Create: `apps/api/app/modules/secrets/__init__.py`
- Create: `apps/api/app/modules/secrets/store.py`
- Modify: `apps/api/tests/unit/test_secret_store.py`

- [ ] **Step 1 : Écrire les tests unitaires FakeSecretStore**

Remplacer le contenu de `apps/api/tests/unit/test_secret_store.py` par :

```python
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
```

- [ ] **Step 2 : Vérifier que les tests échouent**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/unit/test_secret_store.py -v
```

Expected: `FAILED` — `ModuleNotFoundError: No module named 'app.modules.secrets'`

- [ ] **Step 3 : Créer le module `secrets`**

Créer `apps/api/app/modules/secrets/__init__.py` :

```python
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
```

- [ ] **Step 4 : Créer `store.py` avec l'interface et FakeSecretStore**

Créer `apps/api/app/modules/secrets/store.py` :

```python
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
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone


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

        master_key = base64.b64decode(master_key_b64)
        self._aes_key: bytes = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
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
                "owner_type": owner_type or "",
                "owner_id": owner_id or "",
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
            raise SecretNotFoundError(f"Déchiffrement impossible pour {secret_ref}") from e

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
```

- [ ] **Step 5 : Vérifier que les tests unitaires passent**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/unit/test_secret_store.py -v
```

Expected: 7 tests `PASSED`.

- [ ] **Step 6 : Vérifier la suite complète**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/ -q
```

Expected: 75+ tests passent.

- [ ] **Step 7 : Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/api/app/modules/secrets/ apps/api/tests/unit/test_secret_store.py
git commit -m "feat(secrets): SecretStore interface + FakeSecretStore"
```

---

## Task 3: EncryptedDatabaseSecretStore — tests d'intégration

**Files:**
- Create: `apps/api/tests/integration/test_secret_store_db.py`
- Create: `apps/api/app/modules/secrets/deps.py`

Le code de `EncryptedDatabaseSecretStore` est déjà dans `store.py` (Task 2). Cette tâche ajoute les tests d'intégration avec SQLite et crée la dépendance FastAPI.

- [ ] **Step 1 : Écrire les tests d'intégration**

Créer `apps/api/tests/integration/test_secret_store_db.py` :

```python
"""Tests d'intégration — EncryptedDatabaseSecretStore avec SQLite."""
import base64
import json
import os

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
```

- [ ] **Step 2 : Vérifier que les tests passent**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/integration/test_secret_store_db.py -v
```

Expected: 8 tests `PASSED`.

- [ ] **Step 3 : Créer `deps.py` — dépendance FastAPI**

Créer `apps/api/app/modules/secrets/deps.py` :

```python
"""Dépendance FastAPI pour obtenir le SecretStore configuré."""
import os

from app.modules.secrets.store import EncryptedDatabaseSecretStore, SecretStore


def get_secret_store(db) -> SecretStore:
    """Retourne un EncryptedDatabaseSecretStore configuré depuis DEVGATE_MASTER_KEY.

    Lève RuntimeError si la variable d'environnement est absente.
    Ne doit jamais être appelé depuis le frontend ou les logs.
    """
    master_key = os.environ.get("DEVGATE_MASTER_KEY")
    if not master_key:
        raise RuntimeError(
            "DEVGATE_MASTER_KEY non configurée — impossible d'accéder au secret store"
        )
    return EncryptedDatabaseSecretStore(master_key_b64=master_key, db=db)
```

- [ ] **Step 4 : Mettre à jour `__init__.py` pour exporter `get_secret_store`**

Dans `apps/api/app/modules/secrets/__init__.py`, ajouter :

```python
from app.modules.secrets.deps import get_secret_store

__all__ = [
    "SecretStore",
    "FakeSecretStore",
    "EncryptedDatabaseSecretStore",
    "SecretNotFoundError",
    "SecretRevokedError",
    "get_secret_store",
]
```

- [ ] **Step 5 : Vérifier la suite complète**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/ -q
```

Expected: 82+ tests passent.

- [ ] **Step 6 : Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/api/app/modules/secrets/deps.py \
        apps/api/tests/integration/test_secret_store_db.py
git commit -m "feat(secrets): EncryptedDatabaseSecretStore + tests intégration + deps"
```

---

## Task 4: Endpoint admin — stocker un service token

**Files:**
- Modify: `apps/api/app/modules/admin/schemas.py`
- Modify: `apps/api/app/modules/admin/router.py`

- [ ] **Step 1 : Écrire le test d'intégration**

Dans `apps/api/tests/integration/test_admin_router.py` (créer si absent, sinon ajouter à la fin) :

```python
import base64
import json

TEST_MASTER_KEY = base64.b64encode(b"devgate-test-key-32bytes-padding!").decode()


def _make_admin(db_session):
    from app.shared.models import User, AccessGrant, Organization
    org = Organization(id="org-admin", name="Admin Org", slug="admin-org")
    user = User(id="u-admin", email="admin@devgate.test", kind="agency", status="active")
    grant = AccessGrant(id="g-admin", user_id="u-admin", organization_id="org-admin", role="agency_admin")
    db_session.add_all([org, user, grant])
    db_session.commit()


def _make_env_for_token(db_session):
    from app.shared.models import Organization, Project, Environment
    org = Organization(id="org-tok", name="Token Org", slug="tok-org")
    proj = Project(id="proj-tok", organization_id="org-tok", name="P", slug="p")
    env = Environment(
        id="env-tok", project_id="proj-tok", name="E", slug="e",
        kind="staging", public_hostname="e.example.com",
        upstream_hostname="upstream.example.com", status="active",
    )
    db_session.add_all([org, proj, env])
    db_session.commit()


def test_store_service_token_sets_ref(client, db_session, monkeypatch):
    """PUT /admin/environments/{id}/service-token stocke le token et met à jour service_token_ref."""
    monkeypatch.setenv("DEVGATE_MASTER_KEY", TEST_MASTER_KEY)

    _make_admin(db_session)
    _make_env_for_token(db_session)

    from app.modules.auth.service import create_session
    session_id = create_session(db_session, user_id="u-admin")
    client.cookies.set("devgate_session", session_id)

    res = client.put(
        "/admin/environments/env-tok/service-token",
        json={"client_id": "cf-id-123", "client_secret": "cf-secret-456"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["ok"] is True

    from app.shared.models import Environment
    env = db_session.query(Environment).filter(Environment.id == "env-tok").first()
    assert env.service_token_ref is not None
    assert env.service_token_ref.startswith("sec_")


def test_store_service_token_unknown_env_returns_404(client, db_session, monkeypatch):
    monkeypatch.setenv("DEVGATE_MASTER_KEY", TEST_MASTER_KEY)
    _make_admin(db_session)

    from app.modules.auth.service import create_session
    session_id = create_session(db_session, user_id="u-admin")
    client.cookies.set("devgate_session", session_id)

    res = client.put(
        "/admin/environments/env-inexistant/service-token",
        json={"client_id": "x", "client_secret": "y"},
    )
    assert res.status_code == 404
```

Note : Si `create_session` n'existe pas en tant que fonction importable, chercher comment les autres tests admin créent une session admin et reproduire le même pattern.

- [ ] **Step 2 : Vérifier que les tests échouent**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/integration/test_admin_router.py::test_store_service_token_sets_ref -v 2>&1 | tail -15
```

Expected: `FAILED` — 404 ou 405 (endpoint inexistant).

- [ ] **Step 3 : Ajouter `StoreServiceTokenRequest` dans `admin/schemas.py`**

À la fin de `apps/api/app/modules/admin/schemas.py`, ajouter :

```python
class StoreServiceTokenRequest(BaseModel):
    client_id: str
    client_secret: str
```

- [ ] **Step 4 : Ajouter l'endpoint dans `admin/router.py`**

Dans `apps/api/app/modules/admin/router.py`, ajouter les imports manquants en haut :

```python
import json
from app.modules.secrets.deps import get_secret_store
from app.modules.secrets.store import SecretNotFoundError
from app.modules.admin.schemas import StoreServiceTokenRequest  # si pas déjà importé
```

Puis ajouter l'endpoint après `ping_environment` (section Environnements) :

```python
@router.put("/environments/{env_id}/service-token", status_code=200)
def store_service_token(
    env_id: str,
    body: StoreServiceTokenRequest,
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    """Stocke ou remplace le service token Cloudflare Access d'un environnement.
    Le token est chiffré en base — jamais stocké en clair.
    """
    env = db.query(Environment).filter(Environment.id == env_id).first()
    if not env:
        raise NotFoundException()

    secret_store = get_secret_store(db)

    # Révoquer l'ancien token si présent
    if env.service_token_ref:
        try:
            secret_store.revoke(env.service_token_ref)
        except SecretNotFoundError:
            pass  # Déjà absent, idempotent

    payload = json.dumps({"client_id": body.client_id, "client_secret": body.client_secret})
    ref = secret_store.put(
        secret_type="cloudflare_service_token",
        plaintext=payload,
        owner_type="environment",
        owner_id=env_id,
    )
    env.service_token_ref = ref

    audit(
        db,
        actor_user_id=admin.id,
        event_type="admin.service_token.stored",
        target_type="environment",
        target_id=env_id,
        metadata={"has_token": True},
    )
    db.commit()
    return {"ok": True}
```

- [ ] **Step 5 : Vérifier que les tests passent**

D'abord, regarder comment les autres tests admin créent une session admin (chercher `create_session` ou la création de session dans `test_admin_router.py` ou les fixtures). Si la fonction `create_session` n'est pas importable directement, créer la session en base manuellement :

```python
from datetime import datetime, timedelta, timezone
from app.shared.models import Session as SessionModel

session = SessionModel(
    id="s-admin",
    user_id="u-admin",
    expires_at=datetime.now(tz=timezone.utc) + timedelta(days=1),
)
db_session.add(session)
db_session.commit()
client.cookies.set("devgate_session", "s-admin")
```

Adapter les tests si besoin, puis :

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/integration/test_admin_router.py -v -k "service_token" 2>&1 | tail -20
```

Expected: 2 tests `PASSED`.

- [ ] **Step 6 : Vérifier la suite complète**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/ -q
```

Expected: tous les tests passent.

- [ ] **Step 7 : Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/api/app/modules/admin/schemas.py \
        apps/api/app/modules/admin/router.py \
        apps/api/tests/integration/test_admin_router.py
git commit -m "feat(admin): endpoint PUT /environments/{id}/service-token"
```

---

## Task 5: Gateway branché sur SecretStore

**Files:**
- Modify: `apps/api/app/modules/gateway/service.py`
- Modify: `apps/api/app/modules/gateway/router.py`
- Modify: `apps/api/tests/integration/test_gateway.py`

- [ ] **Step 1 : Mettre à jour `service.py` — supprimer les env vars, utiliser SecretStore**

Remplacer la fonction `_get_service_token` et mettre à jour `get_upstream_proxy_headers` dans `apps/api/app/modules/gateway/service.py`.

Ajouter cet import en haut du fichier (après les imports existants) :

```python
import json
from app.modules.secrets.store import SecretStore, SecretNotFoundError, SecretRevokedError
```

Remplacer la fonction `_get_service_token` :

```python
def _get_service_token(token_ref: str, secret_store: SecretStore) -> tuple[str, str]:
    """Récupère les credentials CF Access depuis le SecretStore chiffré.

    Retourne ("", "") si le token est absent, révoqué ou illisible.
    Ne lève jamais d'exception — un token manquant doit résulter en un rejet CF, pas un crash.
    """
    try:
        payload = json.loads(secret_store.get(token_ref))
        return payload.get("client_id", ""), payload.get("client_secret", "")
    except (SecretNotFoundError, SecretRevokedError, Exception):
        return "", ""
```

Mettre à jour la signature de `get_upstream_proxy_headers` pour accepter un `secret_store` optionnel :

```python
def get_upstream_proxy_headers(
    env: Environment,
    user_id: str,
    request_headers: dict,
    secret_store: SecretStore | None = None,
) -> dict:
    """Construit les headers à envoyer à l'upstream.

    - Retire les headers de session et de transport
    - Empêche le spoofing de X-DevGate-User côté client
    - Injecte les credentials CF Access via SecretStore si service_token_ref configuré
    """
    proxy_headers = {
        k: v for k, v in request_headers.items()
        if k.lower() not in ("host", "cookie", "accept-encoding", "x-devgate-user")
    }
    proxy_headers["Accept-Encoding"] = "identity"
    proxy_headers["X-DevGate-User"] = user_id

    if env.service_token_ref and secret_store is not None:
        cf_client_id, cf_client_secret = _get_service_token(env.service_token_ref, secret_store)
        if cf_client_id:
            proxy_headers["CF-Access-Client-Id"] = cf_client_id
        if cf_client_secret:
            proxy_headers["CF-Access-Client-Secret"] = cf_client_secret

    return proxy_headers
```

Mettre à jour la signature de `proxy_request` pour accepter `secret_store` :

```python
async def proxy_request(
    env: Environment,
    method: str,
    path: str,
    headers: dict,
    body: bytes | None,
    user: User,
    db: DbSession,
    secret_store: SecretStore | None = None,
) -> httpx.Response:
    """Proxifie la requête vers l'upstream Cloudflare protégé."""
    if not env.upstream_hostname:
        raise UpstreamUnavailableException("Upstream non configuré")

    upstream_url = f"https://{env.upstream_hostname}{path}"

    proxy_headers = get_upstream_proxy_headers(env, user.id, headers, secret_store)

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            response = await client.request(
                method=method,
                url=upstream_url,
                headers=proxy_headers,
                content=body,
            )
    except httpx.ConnectError as e:
        raise UpstreamUnavailableException(f"Impossible de joindre l'upstream : {e}") from e
    except httpx.TimeoutException as e:
        raise UpstreamUnavailableException("L'upstream n'a pas répondu à temps") from e

    audit(
        db,
        actor_user_id=user.id,
        event_type="gateway.resource.accessed",
        target_type="environment",
        target_id=env.id,
        metadata={"status_code": response.status_code, "path": path},
    )
    db.commit()

    return response
```

Supprimer l'import `from datetime import timezone` si il est devenu inutile (vérifier).

- [ ] **Step 2 : Mettre à jour `router.py` — créer et passer secret_store**

Dans `apps/api/app/modules/gateway/router.py`, ajouter l'import :

```python
from app.modules.secrets.deps import get_secret_store
```

Mettre à jour `gateway_proxy` pour créer le secret_store et le passer :

```python
@router.api_route(
    "/{env_id}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def gateway_proxy(
    env_id: str,
    path: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    env = resolve_environment(env_id, user, db)

    try:
        secret_store = get_secret_store(db)
    except RuntimeError:
        secret_store = None  # DEVGATE_MASTER_KEY absente — CF token non injecté

    body = await request.body()
    upstream_response = await proxy_request(
        env=env,
        method=request.method,
        path=f"/{path}",
        headers=dict(request.headers),
        body=body or None,
        user=user,
        db=db,
        secret_store=secret_store,
    )

    response = Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        media_type=upstream_response.headers.get("content-type"),
    )
    for key, value in upstream_response.headers.multi_items():
        if key.lower() not in _EXCLUDED_RESPONSE_HEADERS:
            response.headers.append(key, value)

    return response
```

Mettre à jour le gestionnaire WebSocket pour passer `secret_store` à `get_upstream_proxy_headers` :

```python
# Juste avant `await websocket.accept()` dans gateway_ws_proxy,
# remplacer le bloc de construction des upstream_headers :

try:
    secret_store = get_secret_store(db)
except RuntimeError:
    secret_store = None

upstream_headers = get_upstream_proxy_headers(env, user.id, {}, secret_store)
ws_extra_headers = list(upstream_headers.items())
```

- [ ] **Step 3 : Mettre à jour le test gateway CF token**

Dans `apps/api/tests/integration/test_gateway.py`, remplacer `test_gateway_injects_cf_service_token` :

```python
@respx.mock
def test_gateway_injects_cf_service_token(client, db_session, monkeypatch):
    """Quand service_token_ref est défini, les headers CF-Access-* sont injectés via SecretStore."""
    import base64
    import json

    TEST_MASTER_KEY = base64.b64encode(b"devgate-test-key-32bytes-padding!").decode()
    monkeypatch.setenv("DEVGATE_MASTER_KEY", TEST_MASTER_KEY)

    _make_user(db_session)
    _make_session(db_session)

    # Stocker le token dans le SecretStore avant de créer l'env
    from app.modules.secrets.store import EncryptedDatabaseSecretStore
    store = EncryptedDatabaseSecretStore(master_key_b64=TEST_MASTER_KEY, db=db_session)
    payload = json.dumps({"client_id": "test-client-id", "client_secret": "test-client-secret"})
    ref = store.put("cloudflare_service_token", payload, owner_type="environment", owner_id="env-gw")
    db_session.commit()

    _make_env(db_session, service_token_ref=ref)

    captured_headers: dict = {}

    def capture(request: httpx.Request, *args, **kwargs) -> httpx.Response:
        captured_headers.update(dict(request.headers))
        return httpx.Response(200, content=b"ok")

    respx.get("https://upstream.cfargotunnel.com/").mock(side_effect=capture)

    client.cookies.set("devgate_session", "s-gw")
    client.get("/gateway/env-gw/")

    assert captured_headers.get("cf-access-client-id") == "test-client-id"
    assert captured_headers.get("cf-access-client-secret") == "test-client-secret"
```

- [ ] **Step 4 : Vérifier que les tests gateway passent**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/integration/test_gateway.py -v
```

Expected: 8 tests `PASSED`.

- [ ] **Step 5 : Vérifier la suite complète**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/ -q
```

Expected: tous les tests passent.

- [ ] **Step 6 : Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/api/app/modules/gateway/service.py \
        apps/api/app/modules/gateway/router.py \
        apps/api/tests/integration/test_gateway.py
git commit -m "feat(gateway): service tokens via SecretStore chiffré — suppression env vars CF"
```
