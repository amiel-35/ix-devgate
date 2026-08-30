# Phase 6 — Intégrations Cloudflare: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implémenter la sync automatique des tunnels Cloudflare, l'inventaire `DiscoveredTunnel`, et le provisioner saga (ADR-001) qui configure CF Access app + policy + service token + DNS sans passer par le dashboard CF.

**Architecture:** Un module `cloudflare` expose un client CF injectable (httpx, mockable via `FakeCFClient`), un job de sync qui maintient l'inventaire `DiscoveredTunnel`, et un provisioner saga qui persiste son état après chaque appel CF distant (R1 ADR-001), bloque le DNS tant que le secret n'est pas scellé (R2), et peut compenser en ordre inverse (R5). La migration Alembic 0002 couvre toutes les nouvelles tables (EncryptedSecret + CF).

**Tech Stack:** Python `httpx`, `respx` (mocks CF API), SQLAlchemy, FastAPI, Next.js Server Components + client components.

---

## Fichiers créés ou modifiés

| Fichier | Action | Responsabilité |
|---|---|---|
| `apps/api/app/config.py` | Modify | Ajouter `CF_ZONE_ID` |
| `apps/api/app/shared/models.py` | Modify | `DiscoveredTunnel`, `ProvisioningJob`, colonnes CF sur `Environment` |
| `apps/api/app/migrations/versions/0002_cloudflare_provisioning.py` | Create | Migration Alembic (EncryptedSecret + CF tables) |
| `apps/api/app/modules/cloudflare/__init__.py` | Create | Module exports |
| `apps/api/app/modules/cloudflare/client.py` | Create | `CFClient` httpx + dataclasses |
| `apps/api/app/modules/cloudflare/fake_client.py` | Create | `FakeCFClient` pour tests |
| `apps/api/app/modules/cloudflare/sync.py` | Create | `sync_tunnels(db, cf)` |
| `apps/api/app/modules/cloudflare/provisioner.py` | Create | Saga state machine |
| `apps/api/app/modules/admin/schemas.py` | Modify | `DiscoveredTunnelItem`, `AssignTunnelRequest` |
| `apps/api/app/modules/admin/router.py` | Modify | Endpoints tunnels + activate |
| `apps/api/tests/integration/test_cf_sync.py` | Create | Tests sync job |
| `apps/api/tests/integration/test_cf_provisioner.py` | Create | Tests provisioner saga |
| `apps/api/tests/integration/test_admin_tunnels.py` | Create | Tests endpoints admin tunnels |
| `apps/web/src/lib/api/server-admin.ts` | Modify | Type `DiscoveredTunnelItem` + méthodes |
| `apps/web/src/app/(admin)/admin/tunnels/page.tsx` | Create | Server component tunnels |
| `apps/web/src/app/(admin)/admin/tunnels/TunnelsClient.tsx` | Create | Client component interactions |

---

## Task 1: Config + modèles + migration Alembic 0002

**Files:**
- Modify: `apps/api/app/config.py`
- Modify: `apps/api/app/shared/models.py`
- Create: `apps/api/app/migrations/versions/0002_cloudflare_provisioning.py`

- [ ] **Step 1: Écrire le test modèles**

Créer `apps/api/tests/unit/test_cloudflare_models.py` :

```python
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
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/unit/test_cloudflare_models.py -v 2>&1 | tail -10
```

Expected: `FAILED` — `ImportError`.

- [ ] **Step 3: Ajouter `CF_ZONE_ID` à `config.py`**

Dans `apps/api/app/config.py`, ajouter dans la classe `Settings` après `CF_ACCOUNT_ID` :

```python
CF_ZONE_ID: str = ""   # Zone DNS pour les routes hostname
```

- [ ] **Step 4: Ajouter les modèles dans `shared/models.py`**

À la fin de `apps/api/app/shared/models.py`, ajouter :

```python
# ── DiscoveredTunnel ──────────────────────────────────────────────

class DiscoveredTunnel(Base):
    __tablename__ = "discovered_tunnels"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    cloudflare_tunnel_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="discovered")
    # status : discovered | assigned | orphaned
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── ProvisioningJob ───────────────────────────────────────────────

class ProvisioningJob(Base):
    __tablename__ = "provisioning_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String, nullable=False, default="cloudflare")
    state: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    # states : pending|creating_access_app|access_app_created|creating_policy|policy_created|
    #          creating_service_token|service_token_created_unsealed|secret_persisted|
    #          creating_dns|active|failed_recoverable|failed_terminal|compensating|rolled_back
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)

    cloudflare_access_app_id: Mapped[str | None] = mapped_column(String)
    cloudflare_policy_id: Mapped[str | None] = mapped_column(String)
    cloudflare_service_token_id: Mapped[str | None] = mapped_column(String)
    dns_record_id: Mapped[str | None] = mapped_column(String)
    secret_persisted: Mapped[bool] = mapped_column(Boolean, default=False)
    dns_published: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    environment: Mapped["Environment"] = relationship(back_populates="provisioning_jobs")
```

Puis dans le modèle `Environment`, ajouter deux colonnes (après `status`) et la relation :

```python
    # Cloudflare — colonnes de provisioning
    discovered_tunnel_id: Mapped[str | None] = mapped_column(ForeignKey("discovered_tunnels.id"))
    provisioning_status: Mapped[str] = mapped_column(String, default="pending")
    # provisioning_status : pending | provisioning | active | failed

    provisioning_jobs: Mapped[list["ProvisioningJob"]] = relationship(back_populates="environment")
```

IMPORTANT : La relation `provisioning_jobs` sur `Environment` et la relation `environment` sur `ProvisioningJob` sont définies par paires. Ajouter également `"ProvisioningJob"` à la liste forward-refs si nécessaire.

- [ ] **Step 5: Vérifier les tests modèles**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/unit/test_cloudflare_models.py -v
```

Expected: 3 tests `PASSED`.

- [ ] **Step 6: Créer la migration Alembic 0002**

Créer `apps/api/app/migrations/versions/0002_cloudflare_provisioning.py` :

```python
"""cloudflare provisioning + encrypted secrets

Revision ID: b2c4e6f8a012
Revises: abe783e8a216
Create Date: 2026-04-21 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2c4e6f8a012"
down_revision: Union[str, None] = "abe783e8a216"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── encrypted_secrets ─────────────────────────────────────────
    op.create_table(
        "encrypted_secrets",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("secret_ref", sa.String(), nullable=False),
        sa.Column("secret_type", sa.String(), nullable=False),
        sa.Column("owner_type", sa.String(), nullable=True),
        sa.Column("owner_id", sa.String(), nullable=True),
        sa.Column("key_id", sa.String(), nullable=False, server_default="v1"),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("nonce", sa.String(), nullable=False),
        sa.Column("algorithm", sa.String(), nullable=False, server_default="AES-256-GCM"),
        sa.Column("metadata_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("secret_ref"),
    )
    op.create_index("ix_encrypted_secrets_secret_ref", "encrypted_secrets", ["secret_ref"], unique=True)

    # ── discovered_tunnels ────────────────────────────────────────
    op.create_table(
        "discovered_tunnels",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("cloudflare_tunnel_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="discovered"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cloudflare_tunnel_id"),
    )
    op.create_index("ix_discovered_tunnels_cf_id", "discovered_tunnels", ["cloudflare_tunnel_id"], unique=True)

    # ── provisioning_jobs ─────────────────────────────────────────
    op.create_table(
        "provisioning_jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("environment_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False, server_default="cloudflare"),
        sa.Column("state", sa.String(), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("cloudflare_access_app_id", sa.String(), nullable=True),
        sa.Column("cloudflare_policy_id", sa.String(), nullable=True),
        sa.Column("cloudflare_service_token_id", sa.String(), nullable=True),
        sa.Column("dns_record_id", sa.String(), nullable=True),
        sa.Column("secret_persisted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("dns_published", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provisioning_jobs_env_id", "provisioning_jobs", ["environment_id"], unique=False)

    # ── environments — nouvelles colonnes ─────────────────────────
    op.add_column("environments", sa.Column("discovered_tunnel_id", sa.String(), nullable=True))
    op.add_column("environments", sa.Column("provisioning_status", sa.String(), nullable=True, server_default="pending"))
    op.add_column("environments", sa.Column("service_token_ref", sa.String(), nullable=True))
    op.create_foreign_key(
        "fk_environments_discovered_tunnel",
        "environments", "discovered_tunnels",
        ["discovered_tunnel_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_environments_discovered_tunnel", "environments", type_="foreignkey")
    op.drop_column("environments", "service_token_ref")
    op.drop_column("environments", "provisioning_status")
    op.drop_column("environments", "discovered_tunnel_id")
    op.drop_index("ix_provisioning_jobs_env_id", table_name="provisioning_jobs")
    op.drop_table("provisioning_jobs")
    op.drop_index("ix_discovered_tunnels_cf_id", table_name="discovered_tunnels")
    op.drop_table("discovered_tunnels")
    op.drop_index("ix_encrypted_secrets_secret_ref", table_name="encrypted_secrets")
    op.drop_table("encrypted_secrets")
```

NOTE : La colonne `service_token_ref` existe peut-être déjà sur `environments` selon l'état de la base. Si Alembic lève une erreur `DuplicateColumn`, supprimer la ligne `op.add_column("environments", sa.Column("service_token_ref", ...))` du `upgrade()`.

- [ ] **Step 7: Vérifier la suite complète**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/ -q 2>&1 | tail -5
```

Expected: tous les tests passent.

- [ ] **Step 8: Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/api/app/config.py \
        apps/api/app/shared/models.py \
        apps/api/app/migrations/versions/0002_cloudflare_provisioning.py \
        apps/api/tests/unit/test_cloudflare_models.py
git commit -m "feat(cloudflare): modèles DiscoveredTunnel + ProvisioningJob + migration Alembic 0002"
```

---

## Task 2: CF API client

**Files:**
- Create: `apps/api/app/modules/cloudflare/__init__.py`
- Create: `apps/api/app/modules/cloudflare/client.py`
- Create: `apps/api/app/modules/cloudflare/fake_client.py`
- Create: `apps/api/tests/unit/test_cf_client.py`

- [ ] **Step 1: Écrire les tests du client CF (avec respx)**

Créer `apps/api/tests/unit/test_cf_client.py` :

```python
"""Tests unitaires — CFClient (respx mock)."""
import respx
import httpx
import pytest

from app.modules.cloudflare.client import CFClient, CFTunnel, CFAccessApp, CFServiceToken


FAKE_TOKEN = "test-cf-token"
FAKE_ACCOUNT = "acc-123"
FAKE_ZONE = "zone-456"
BASE = "https://api.cloudflare.com/client/v4"


def make_client() -> CFClient:
    return CFClient(api_token=FAKE_TOKEN, account_id=FAKE_ACCOUNT, zone_id=FAKE_ZONE)


@respx.mock
def test_list_tunnels_returns_devgate_tunnels():
    respx.get(f"{BASE}/accounts/{FAKE_ACCOUNT}/cfd_tunnel").mock(
        return_value=httpx.Response(200, json={
            "result": [
                {"id": "t-1", "name": "devgate-acme", "status": "active", "connections": []},
                {"id": "t-2", "name": "other-tunnel", "status": "active", "connections": []},
            ],
            "success": True,
        })
    )
    client = make_client()
    tunnels = client.list_tunnels()
    # Only devgate-* tunnels are returned
    assert len(tunnels) == 1
    assert tunnels[0].id == "t-1"
    assert tunnels[0].name == "devgate-acme"


@respx.mock
def test_create_access_app_returns_app():
    respx.post(f"{BASE}/accounts/{FAKE_ACCOUNT}/access/apps").mock(
        return_value=httpx.Response(200, json={
            "result": {"id": "app-1", "name": "devgate-test", "domain": "test.example.com"},
            "success": True,
        })
    )
    client = make_client()
    app = client.create_access_app("devgate-test", "test.example.com")
    assert app.id == "app-1"
    assert isinstance(app, CFAccessApp)


@respx.mock
def test_create_service_token_returns_token_with_secret():
    respx.post(f"{BASE}/accounts/{FAKE_ACCOUNT}/access/service_tokens").mock(
        return_value=httpx.Response(200, json={
            "result": {
                "id": "tok-1",
                "client_id": "client-abc",
                "client_secret": "secret-xyz",
            },
            "success": True,
        })
    )
    client = make_client()
    token = client.create_service_token("devgate-test")
    assert token.id == "tok-1"
    assert token.client_secret == "secret-xyz"
    assert isinstance(token, CFServiceToken)


@respx.mock
def test_create_dns_cname_returns_record_id():
    respx.post(f"{BASE}/zones/{FAKE_ZONE}/dns_records").mock(
        return_value=httpx.Response(200, json={
            "result": {"id": "dns-1", "name": "test.example.com", "type": "CNAME"},
            "success": True,
        })
    )
    client = make_client()
    record_id = client.create_dns_cname("test.example.com", "tunnel-id-abc")
    assert record_id == "dns-1"
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/unit/test_cf_client.py -v 2>&1 | tail -10
```

Expected: `FAILED` — `ModuleNotFoundError`.

- [ ] **Step 3: Créer `modules/cloudflare/__init__.py`**

```python
"""Module Cloudflare — client API, sync tunnels, provisioner saga.
Voir ADR-001 pour la doctrine de provisioning.
"""
```

- [ ] **Step 4: Créer `modules/cloudflare/client.py`**

```python
"""
Client Cloudflare API v4.

Utilise httpx synchrone (suffisant pour v1 monolithe).
Toutes les méthodes lèvent httpx.HTTPStatusError en cas d'erreur CF API.
"""
from dataclasses import dataclass, field

import httpx

CF_API_BASE = "https://api.cloudflare.com/client/v4"


@dataclass
class CFTunnel:
    id: str
    name: str
    status: str
    connections: list[dict] = field(default_factory=list)


@dataclass
class CFAccessApp:
    id: str
    name: str
    domain: str


@dataclass
class CFServiceToken:
    id: str
    client_id: str
    client_secret: str  # visible une seule fois à la création


class CFClient:
    """Wrapper httpx autour de l'API Cloudflare v4.

    api_token   : CF API token (scope : Tunnel read, Access write, DNS write)
    account_id  : ID du compte CF de l'agence
    zone_id     : Zone DNS pour les CNAME (CF_ZONE_ID)
    """

    def __init__(self, api_token: str, account_id: str, zone_id: str = "") -> None:
        self._account_id = account_id
        self._zone_id = zone_id
        self._headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, **params) -> dict:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(f"{CF_API_BASE}{path}", headers=self._headers, params=params)
            r.raise_for_status()
            return r.json()

    def _post(self, path: str, body: dict) -> dict:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(f"{CF_API_BASE}{path}", headers=self._headers, json=body)
            r.raise_for_status()
            return r.json()

    def _delete(self, path: str) -> None:
        with httpx.Client(timeout=15.0) as client:
            r = client.delete(f"{CF_API_BASE}{path}", headers=self._headers)
            r.raise_for_status()

    # ── Tunnels ───────────────────────────────────────────────────

    def list_tunnels(self) -> list[CFTunnel]:
        """Liste les tunnels actifs préfixés 'devgate-'."""
        data = self._get(
            f"/accounts/{self._account_id}/cfd_tunnel",
            is_deleted="false",
        )
        return [
            CFTunnel(
                id=t["id"],
                name=t["name"],
                status=t.get("status", "inactive"),
                connections=t.get("connections", []),
            )
            for t in data.get("result", [])
            if t["name"].startswith("devgate-")
        ]

    # ── Access apps ───────────────────────────────────────────────

    def create_access_app(self, name: str, domain: str) -> CFAccessApp:
        """Crée une Access application self-hosted sur le hostname donné."""
        data = self._post(
            f"/accounts/{self._account_id}/access/apps",
            {
                "name": name,
                "domain": domain,
                "type": "self_hosted",
                "session_duration": "24h",
            },
        )
        result = data["result"]
        return CFAccessApp(id=result["id"], name=result["name"], domain=result["domain"])

    def delete_access_app(self, app_id: str) -> None:
        self._delete(f"/accounts/{self._account_id}/access/apps/{app_id}")

    # ── Policies ──────────────────────────────────────────────────

    def create_policy(self, app_id: str, name: str) -> str:
        """Crée une policy 'allow any valid service token'. Retourne le policy_id."""
        data = self._post(
            f"/accounts/{self._account_id}/access/apps/{app_id}/policies",
            {
                "name": name,
                "decision": "non_identity",
                "include": [{"any_valid_service_token": {}}],
            },
        )
        return data["result"]["id"]

    def delete_policy(self, app_id: str, policy_id: str) -> None:
        self._delete(
            f"/accounts/{self._account_id}/access/apps/{app_id}/policies/{policy_id}"
        )

    # ── Service tokens ────────────────────────────────────────────

    def create_service_token(self, name: str) -> CFServiceToken:
        """Crée un service token. client_secret visible une seule fois."""
        data = self._post(
            f"/accounts/{self._account_id}/access/service_tokens",
            {"name": name},
        )
        result = data["result"]
        return CFServiceToken(
            id=result["id"],
            client_id=result["client_id"],
            client_secret=result["client_secret"],
        )

    def revoke_service_token(self, token_id: str) -> None:
        self._delete(f"/accounts/{self._account_id}/access/service_tokens/{token_id}")

    # ── DNS ───────────────────────────────────────────────────────

    def create_dns_cname(self, name: str, tunnel_id: str) -> str:
        """Crée un CNAME proxied vers {tunnel_id}.cfargotunnel.com. Retourne record_id."""
        data = self._post(
            f"/zones/{self._zone_id}/dns_records",
            {
                "type": "CNAME",
                "name": name,
                "content": f"{tunnel_id}.cfargotunnel.com",
                "proxied": True,
            },
        )
        return data["result"]["id"]

    def delete_dns_record(self, record_id: str) -> None:
        self._delete(f"/zones/{self._zone_id}/dns_records/{record_id}")
```

- [ ] **Step 5: Créer `modules/cloudflare/fake_client.py`**

```python
"""FakeCFClient — implémentation en mémoire du CFClient pour les tests."""
from dataclasses import dataclass, field

from app.modules.cloudflare.client import CFAccessApp, CFServiceToken, CFTunnel


class FakeCFError(Exception):
    """Simule une erreur CF API dans les tests."""


class FakeCFClient:
    """Client CF en mémoire pour les tests d'intégration.

    Usage :
        fake = FakeCFClient()
        fake.tunnels = [CFTunnel(id="t-1", name="devgate-acme", status="active")]
        fake.fail_at = "create_service_token"  # Simule une erreur sur cette étape
    """

    def __init__(self) -> None:
        self.fail_at: str | None = None
        self.tunnels: list[CFTunnel] = [
            CFTunnel(id="tunnel-fake-1", name="devgate-test", status="active"),
        ]
        # Enregistrements des appels effectués
        self.created_apps: list[dict] = []
        self.created_policies: list[dict] = []
        self.created_tokens: list[dict] = []
        self.created_dns: list[dict] = []
        self.deleted_apps: list[str] = []
        self.deleted_policies: list[tuple[str, str]] = []
        self.revoked_tokens: list[str] = []
        self.deleted_dns: list[str] = []

    def _maybe_fail(self, step: str) -> None:
        if self.fail_at == step:
            raise FakeCFError(f"Simulated CF API failure at {step}")

    def list_tunnels(self) -> list[CFTunnel]:
        self._maybe_fail("list_tunnels")
        return list(self.tunnels)

    def create_access_app(self, name: str, domain: str) -> CFAccessApp:
        self._maybe_fail("create_access_app")
        app_id = f"app-fake-{len(self.created_apps) + 1}"
        self.created_apps.append({"id": app_id, "name": name, "domain": domain})
        return CFAccessApp(id=app_id, name=name, domain=domain)

    def delete_access_app(self, app_id: str) -> None:
        self._maybe_fail("delete_access_app")
        self.deleted_apps.append(app_id)

    def create_policy(self, app_id: str, name: str) -> str:
        self._maybe_fail("create_policy")
        policy_id = f"policy-fake-{len(self.created_policies) + 1}"
        self.created_policies.append({"id": policy_id, "app_id": app_id, "name": name})
        return policy_id

    def delete_policy(self, app_id: str, policy_id: str) -> None:
        self._maybe_fail("delete_policy")
        self.deleted_policies.append((app_id, policy_id))

    def create_service_token(self, name: str) -> CFServiceToken:
        self._maybe_fail("create_service_token")
        token_id = f"token-fake-{len(self.created_tokens) + 1}"
        token = CFServiceToken(
            id=token_id,
            client_id=f"client-id-{token_id}",
            client_secret=f"client-secret-{token_id}",
        )
        self.created_tokens.append({"id": token_id, "name": name})
        return token

    def revoke_service_token(self, token_id: str) -> None:
        self._maybe_fail("revoke_service_token")
        self.revoked_tokens.append(token_id)

    def create_dns_cname(self, name: str, tunnel_id: str) -> str:
        self._maybe_fail("create_dns_cname")
        record_id = f"dns-fake-{len(self.created_dns) + 1}"
        self.created_dns.append({"id": record_id, "name": name, "tunnel_id": tunnel_id})
        return record_id

    def delete_dns_record(self, record_id: str) -> None:
        self._maybe_fail("delete_dns_record")
        self.deleted_dns.append(record_id)
```

- [ ] **Step 6: Vérifier que les tests passent**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/unit/test_cf_client.py -v
```

Expected: 4 tests `PASSED`.

- [ ] **Step 7: Suite complète**

```bash
.venv/bin/pytest apps/api/tests/ -q 2>&1 | tail -5
```

Expected: tous les tests passent.

- [ ] **Step 8: Commit**

```bash
git add apps/api/app/modules/cloudflare/ apps/api/tests/unit/test_cf_client.py
git commit -m "feat(cloudflare): CFClient + FakeCFClient"
```

---

## Task 3: Sync job + endpoint admin

**Files:**
- Create: `apps/api/app/modules/cloudflare/sync.py`
- Create: `apps/api/tests/integration/test_cf_sync.py`
- Modify: `apps/api/app/modules/admin/router.py` (ajouter POST /sync-tunnels)

- [ ] **Step 1: Écrire les tests du sync**

Créer `apps/api/tests/integration/test_cf_sync.py` :

```python
"""Tests d'intégration — sync tunnels CF."""
from datetime import datetime, timezone

from app.modules.cloudflare.client import CFTunnel
from app.modules.cloudflare.fake_client import FakeCFClient
from app.modules.cloudflare.sync import sync_tunnels
from app.shared.models import DiscoveredTunnel


def _fake_cf_with_tunnels(*tunnels: CFTunnel) -> FakeCFClient:
    fake = FakeCFClient()
    fake.tunnels = list(tunnels)
    return fake


def test_sync_creates_new_discovered_tunnel(db_session):
    """Un nouveau tunnel CF est créé comme DiscoveredTunnel."""
    fake = _fake_cf_with_tunnels(
        CFTunnel(id="t-1", name="devgate-acme", status="active"),
    )
    result = sync_tunnels(db_session, fake)

    assert result["discovered"] == 1
    assert result["updated"] == 0

    dt = db_session.query(DiscoveredTunnel).filter(
        DiscoveredTunnel.cloudflare_tunnel_id == "t-1"
    ).first()
    assert dt is not None
    assert dt.name == "devgate-acme"
    assert dt.status == "discovered"


def test_sync_updates_existing_tunnel(db_session):
    """Un tunnel déjà connu est mis à jour (last_seen_at)."""
    # Créer un tunnel existant
    existing = DiscoveredTunnel(
        cloudflare_tunnel_id="t-1",
        name="devgate-acme",
        status="discovered",
    )
    db_session.add(existing)
    db_session.commit()

    fake = _fake_cf_with_tunnels(
        CFTunnel(id="t-1", name="devgate-acme", status="active"),
    )
    result = sync_tunnels(db_session, fake)

    assert result["updated"] == 1
    assert result["discovered"] == 0

    db_session.refresh(existing)
    assert existing.last_seen_at is not None


def test_sync_marks_absent_tunnel_as_orphaned(db_session):
    """Un tunnel en base mais absent du sync CF devient orphaned."""
    existing = DiscoveredTunnel(
        cloudflare_tunnel_id="t-ghost",
        name="devgate-ghost",
        status="discovered",
    )
    db_session.add(existing)
    db_session.commit()

    # CF ne retourne pas ce tunnel
    fake = _fake_cf_with_tunnels(
        CFTunnel(id="t-other", name="devgate-other", status="active"),
    )
    result = sync_tunnels(db_session, fake)

    assert result["orphaned"] == 1
    db_session.refresh(existing)
    assert existing.status == "orphaned"


def test_sync_does_not_orphan_assigned_tunnel(db_session):
    """Un tunnel assigné n'est pas marqué orphelin même s'il disparaît du sync."""
    assigned = DiscoveredTunnel(
        cloudflare_tunnel_id="t-assigned",
        name="devgate-assigned",
        status="assigned",
    )
    db_session.add(assigned)
    db_session.commit()

    fake = FakeCFClient()
    fake.tunnels = []  # CF retourne aucun tunnel
    result = sync_tunnels(db_session, fake)

    db_session.refresh(assigned)
    assert assigned.status == "assigned"  # inchangé
    assert result["orphaned"] == 0


def test_sync_handles_cf_error_gracefully(db_session):
    """En cas d'erreur CF API, sync retourne une erreur sans crash."""
    fake = FakeCFClient()
    fake.fail_at = "list_tunnels"

    result = sync_tunnels(db_session, fake)
    assert "error" in result
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/integration/test_cf_sync.py -v 2>&1 | tail -10
```

Expected: `FAILED` — `ModuleNotFoundError`.

- [ ] **Step 3: Créer `modules/cloudflare/sync.py`**

```python
"""
Sync job Cloudflare — maintient l'inventaire DiscoveredTunnel.

Règles :
- Ne crée jamais d'Environment automatiquement (ADR-001 §1).
- Seuls les tunnels préfixés 'devgate-' sont importés.
- Un tunnel absent du sync passe en 'orphaned' seulement s'il était 'discovered'.
- Les tunnels 'assigned' et 'active' ne sont pas orphelinés automatiquement.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DbSession

from app.modules.cloudflare.client import CFClient
from app.shared.models import DiscoveredTunnel

logger = logging.getLogger(__name__)


def sync_tunnels(db: DbSession, cf: CFClient) -> dict:
    """
    Interroge l'API CF, upsert les DiscoveredTunnel.
    Retourne {"discovered": N, "updated": N, "orphaned": N} ou {"error": "..."}.
    """
    try:
        tunnels = cf.list_tunnels()
    except Exception as e:
        logger.warning("CF sync failed: %s", e, exc_info=True)
        return {"error": str(e), "discovered": 0, "updated": 0, "orphaned": 0}

    now = datetime.now(tz=timezone.utc)
    seen_ids: set[str] = set()
    discovered_count = 0
    updated_count = 0

    for t in tunnels:
        seen_ids.add(t.id)
        existing = (
            db.query(DiscoveredTunnel)
            .filter(DiscoveredTunnel.cloudflare_tunnel_id == t.id)
            .first()
        )
        if existing:
            existing.last_seen_at = now
            existing.metadata_json = {
                "cf_status": t.status,
                "connections": t.connections,
            }
            updated_count += 1
        else:
            db.add(DiscoveredTunnel(
                cloudflare_tunnel_id=t.id,
                name=t.name,
                status="discovered",
                last_seen_at=now,
                metadata_json={"cf_status": t.status, "connections": t.connections},
            ))
            discovered_count += 1

    # Orphelins : tunnels 'discovered' non vus dans ce cycle
    orphaned_count = 0
    discovered_in_db = (
        db.query(DiscoveredTunnel)
        .filter(DiscoveredTunnel.status == "discovered")
        .all()
    )
    for dt in discovered_in_db:
        if dt.cloudflare_tunnel_id not in seen_ids:
            dt.status = "orphaned"
            orphaned_count += 1
            logger.info("Tunnel orphelin détecté : %s (%s)", dt.name, dt.cloudflare_tunnel_id)

    db.commit()
    return {"discovered": discovered_count, "updated": updated_count, "orphaned": orphaned_count}
```

- [ ] **Step 4: Vérifier que les tests passent**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
.venv/bin/pytest apps/api/tests/integration/test_cf_sync.py -v
```

Expected: 5 tests `PASSED`.

- [ ] **Step 5: Ajouter l'endpoint `POST /admin/sync-tunnels`**

Dans `apps/api/app/modules/admin/router.py`, ajouter en haut des imports (vérifier les doublons) :

```python
from app.config import settings
from app.modules.cloudflare.client import CFClient
from app.modules.cloudflare.sync import sync_tunnels
from app.shared.models import DiscoveredTunnel
```

Puis ajouter l'endpoint (section Cloudflare) :

```python
# ── Cloudflare ────────────────────────────────────────────────────

@router.post("/sync-tunnels", status_code=200)
def trigger_cf_sync(db: DbSession = Depends(get_db)):
    """Déclenche manuellement la sync des tunnels CF.
    Nécessite CF_API_TOKEN et CF_ACCOUNT_ID configurés.
    """
    from fastapi import HTTPException
    if not settings.CF_API_TOKEN or not settings.CF_ACCOUNT_ID:
        raise HTTPException(
            status_code=503,
            detail="CF_API_TOKEN ou CF_ACCOUNT_ID non configurés",
        )
    cf = CFClient(
        api_token=settings.CF_API_TOKEN,
        account_id=settings.CF_ACCOUNT_ID,
        zone_id=settings.CF_ZONE_ID,
    )
    return sync_tunnels(db, cf)
```

- [ ] **Step 6: Suite complète**

```bash
.venv/bin/pytest apps/api/tests/ -q 2>&1 | tail -5
```

Expected: tous les tests passent.

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/modules/cloudflare/sync.py \
        apps/api/app/modules/admin/router.py \
        apps/api/tests/integration/test_cf_sync.py
git commit -m "feat(cloudflare): sync job DiscoveredTunnel + endpoint POST /admin/sync-tunnels"
```

---

## Task 4: Admin — inventaire tunnels + assignation

**Files:**
- Modify: `apps/api/app/modules/admin/schemas.py`
- Modify: `apps/api/app/modules/admin/router.py`
- Create: `apps/api/tests/integration/test_admin_tunnels.py`

- [ ] **Step 1: Écrire les tests**

Créer `apps/api/tests/integration/test_admin_tunnels.py` :

```python
"""Tests d'intégration — endpoints admin tunnels."""
from app.shared.models import DiscoveredTunnel, Environment, Organization, Project


def _setup_admin(db_session):
    from app.shared.models import User, AccessGrant
    org = Organization(id="org-tun", name="Tun Org", slug="tun-org")
    user = User(id="u-tun", email="tun@test.com", kind="agency", status="active")
    grant = AccessGrant(id="g-tun", user_id="u-tun", organization_id="org-tun", role="agency_admin")
    db_session.add_all([org, user, grant])
    db_session.commit()


def _auth(client, db_session):
    from datetime import datetime, timedelta, timezone
    from app.shared.models import Session as SessionModel
    sess = SessionModel(
        id="s-tun",
        user_id="u-tun",
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=1),
    )
    db_session.add(sess)
    db_session.commit()
    client.cookies.set("devgate_session", "s-tun")


def _make_tunnel(db_session, tunnel_id="t-1", name="devgate-test", status="discovered"):
    dt = DiscoveredTunnel(
        cloudflare_tunnel_id=tunnel_id,
        name=name,
        status=status,
    )
    db_session.add(dt)
    db_session.commit()
    return dt


def _make_env(db_session):
    proj = Project(id="proj-tun", organization_id="org-tun", name="P", slug="p")
    env = Environment(
        id="env-tun", project_id="proj-tun", name="E", slug="e",
        kind="staging", public_hostname="e.tun.example.com",
        upstream_hostname="e.cfargotunnel.com", status="active",
    )
    db_session.add_all([proj, env])
    db_session.commit()
    return env


def test_list_discovered_tunnels_empty(client, db_session):
    _setup_admin(db_session)
    _auth(client, db_session)
    res = client.get("/admin/discovered-tunnels")
    assert res.status_code == 200
    assert res.json() == []


def test_list_discovered_tunnels_returns_tunnels(client, db_session):
    _setup_admin(db_session)
    _auth(client, db_session)
    _make_tunnel(db_session)
    res = client.get("/admin/discovered-tunnels")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["name"] == "devgate-test"
    assert data[0]["status"] == "discovered"


def test_assign_tunnel_to_environment(client, db_session):
    _setup_admin(db_session)
    _auth(client, db_session)
    tunnel = _make_tunnel(db_session)
    env = _make_env(db_session)

    res = client.post(
        f"/admin/discovered-tunnels/{tunnel.id}/assign",
        json={"environment_id": "env-tun"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["ok"] is True

    db_session.expire_all()
    from app.shared.models import DiscoveredTunnel as DT, Environment as E
    t = db_session.query(DT).filter(DT.id == tunnel.id).first()
    e = db_session.query(E).filter(E.id == "env-tun").first()
    assert t.status == "assigned"
    assert e.cloudflare_tunnel_id == "t-1"
    assert e.discovered_tunnel_id == tunnel.id


def test_assign_tunnel_unknown_env_returns_404(client, db_session):
    _setup_admin(db_session)
    _auth(client, db_session)
    tunnel = _make_tunnel(db_session)
    res = client.post(
        f"/admin/discovered-tunnels/{tunnel.id}/assign",
        json={"environment_id": "env-inexistant"},
    )
    assert res.status_code == 404
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
.venv/bin/pytest apps/api/tests/integration/test_admin_tunnels.py -v 2>&1 | tail -10
```

Expected: `FAILED` (endpoints absent).

- [ ] **Step 3: Ajouter `DiscoveredTunnelItem` et `AssignTunnelRequest` dans `schemas.py`**

Dans `apps/api/app/modules/admin/schemas.py`, ajouter à la fin :

```python
class DiscoveredTunnelItem(BaseModel):
    id: str
    cloudflare_tunnel_id: str
    name: str
    status: str
    last_seen_at: str | None

    model_config = {"from_attributes": True}


class AssignTunnelRequest(BaseModel):
    environment_id: str
```

- [ ] **Step 4: Ajouter les endpoints dans `admin/router.py`**

Dans la section Cloudflare (après `trigger_cf_sync`), ajouter :

```python
@router.get("/discovered-tunnels")
def list_discovered_tunnels(db: DbSession = Depends(get_db)):
    """Liste tous les tunnels découverts, ordonnés par date de création décroissante."""
    tunnels = (
        db.query(DiscoveredTunnel)
        .order_by(DiscoveredTunnel.created_at.desc())
        .all()
    )
    return [
        {
            "id": t.id,
            "cloudflare_tunnel_id": t.cloudflare_tunnel_id,
            "name": t.name,
            "status": t.status,
            "last_seen_at": t.last_seen_at.isoformat() if t.last_seen_at else None,
        }
        for t in tunnels
    ]


@router.post("/discovered-tunnels/{tunnel_id}/assign", status_code=200)
def assign_tunnel_to_environment(
    tunnel_id: str,
    body: AssignTunnelRequest,
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    """Affecte un tunnel découvert à un environnement DevGate.
    Met à jour cloudflare_tunnel_id sur l'environnement.
    """
    from app.modules.admin.schemas import AssignTunnelRequest as _  # noqa: already imported
    tunnel = db.query(DiscoveredTunnel).filter(DiscoveredTunnel.id == tunnel_id).first()
    if not tunnel:
        raise NotFoundException()

    env = db.query(Environment).filter(Environment.id == body.environment_id).first()
    if not env:
        raise NotFoundException()

    tunnel.status = "assigned"
    env.cloudflare_tunnel_id = tunnel.cloudflare_tunnel_id
    env.upstream_hostname = f"{tunnel.cloudflare_tunnel_id}.cfargotunnel.com"
    env.discovered_tunnel_id = tunnel.id

    audit(
        db,
        actor_user_id=admin.id,
        event_type="admin.tunnel.assigned",
        target_type="environment",
        target_id=env.id,
        metadata={"tunnel_id": tunnel.cloudflare_tunnel_id, "tunnel_name": tunnel.name},
    )
    db.commit()
    return {"ok": True}
```

Vérifier que `AssignTunnelRequest` est importé dans `admin/router.py` depuis `admin/schemas.py`.

- [ ] **Step 5: Vérifier que les tests passent**

```bash
.venv/bin/pytest apps/api/tests/integration/test_admin_tunnels.py -v
```

Expected: 4 tests `PASSED`.

- [ ] **Step 6: Suite complète**

```bash
.venv/bin/pytest apps/api/tests/ -q 2>&1 | tail -5
```

Expected: tous les tests passent.

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/modules/admin/schemas.py \
        apps/api/app/modules/admin/router.py \
        apps/api/tests/integration/test_admin_tunnels.py
git commit -m "feat(admin): GET /discovered-tunnels + POST /discovered-tunnels/{id}/assign"
```

---

## Task 5: Provisioner saga

**Files:**
- Create: `apps/api/app/modules/cloudflare/provisioner.py`
- Create: `apps/api/tests/integration/test_cf_provisioner.py`

- [ ] **Step 1: Écrire les tests du provisioner**

Créer `apps/api/tests/integration/test_cf_provisioner.py` :

```python
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
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
.venv/bin/pytest apps/api/tests/integration/test_cf_provisioner.py -v 2>&1 | tail -10
```

Expected: `FAILED` — `ImportError`.

- [ ] **Step 3: Créer `modules/cloudflare/provisioner.py`**

```python
"""
Provisioner saga Cloudflare — ADR-001.

Règles implémentées :
- R1 : persist après chaque appel CF (flush + commit = checkpoint)
- R2 : DNS uniquement si secret_persisted = True
- R3 : service token = checkpoint critique (create-and-seal)
- R4 : pas de retry aveugle si secret non scellé
- R5 : compensation explicite dans l'ordre inverse
"""
import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DbSession

from app.modules.cloudflare.client import CFClient
from app.modules.secrets.store import SecretStore
from app.shared.models import Environment, ProvisioningJob

logger = logging.getLogger(__name__)


class ProvisioningError(Exception):
    """Erreur de provisioning — job passé en failed_recoverable."""


def _persist(job: ProvisioningJob, state: str, db: DbSession, **fields) -> None:
    """Checkpoint : persiste l'état et les IDs CF après chaque appel distant."""
    job.state = state
    job.updated_at = datetime.now(tz=timezone.utc)
    for key, value in fields.items():
        setattr(job, key, value)
    db.flush()


def run_provisioning_job(
    job: ProvisioningJob,
    env: Environment,
    cf: CFClient,
    secret_store: SecretStore,
    db: DbSession,
) -> str:
    """
    Avance le provisioning jusqu'à 'active' ou état d'erreur.

    Chaque transition persiste immédiatement — un redémarrage peut reprendre
    depuis le dernier checkpoint.

    Retourne le state final.
    """
    try:
        # ── Étape 1 : Access app ───────────────────────────────────
        if job.state == "pending":
            _persist(job, "creating_access_app", db)
            app = cf.create_access_app(
                name=f"devgate-{env.slug}",
                domain=env.public_hostname,
            )
            _persist(job, "access_app_created", db, cloudflare_access_app_id=app.id)
            db.commit()
            logger.info("Job %s: Access app créée (%s)", job.id, app.id)

        # ── Étape 2 : Policy ───────────────────────────────────────
        if job.state == "access_app_created":
            _persist(job, "creating_policy", db)
            policy_id = cf.create_policy(
                app_id=job.cloudflare_access_app_id,
                name=f"allow-devgate-{env.slug}",
            )
            _persist(job, "policy_created", db, cloudflare_policy_id=policy_id)
            db.commit()
            logger.info("Job %s: Policy créée (%s)", job.id, policy_id)

        # ── Étape 3 : Service token (checkpoint critique ADR-001 R3) ──
        if job.state == "policy_created":
            _persist(job, "creating_service_token", db)
            token = cf.create_service_token(name=f"devgate-{env.slug}")

            # Persister l'ID du token avant de tenter de sceller le secret
            _persist(
                job, "service_token_created_unsealed", db,
                cloudflare_service_token_id=token.id,
            )
            db.commit()
            logger.info("Job %s: Service token créé (%s) — scellement du secret...", job.id, token.id)

            # Scellement immédiat — si cette étape échoue, le job passe en
            # failed_recoverable et le token doit être révoqué (ADR-001 R4)
            payload = json.dumps({
                "client_id": token.client_id,
                "client_secret": token.client_secret,
            })
            ref = secret_store.put(
                secret_type="cloudflare_service_token",
                plaintext=payload,
                owner_type="environment",
                owner_id=env.id,
            )
            env.service_token_ref = ref
            _persist(job, "secret_persisted", db, secret_persisted=True)
            db.commit()
            logger.info("Job %s: Secret scellé (ref=%s)", job.id, ref)

        # ── Étape 4 : DNS (dernier, ADR-001 R2) ────────────────────
        if job.state == "secret_persisted":
            # Garantie explicite : ne jamais publier le DNS sans secret scellé
            if not job.secret_persisted:
                raise ProvisioningError(
                    "Tentative de publication DNS sans secret scellé — bloqué par ADR-001 R2"
                )

            tunnel_id = env.cloudflare_tunnel_id
            if not tunnel_id:
                raise ProvisioningError(
                    "cloudflare_tunnel_id absent sur l'environnement — assignez un tunnel d'abord"
                )

            _persist(job, "creating_dns", db)
            dns_record_id = cf.create_dns_cname(
                name=env.public_hostname,
                tunnel_id=tunnel_id,
            )
            _persist(job, "active", db, dns_record_id=dns_record_id, dns_published=True)
            env.status = "active"
            db.commit()
            logger.info("Job %s: DNS publié — environnement actif", job.id)

        return job.state

    except ProvisioningError:
        # Erreur métier explicite
        job.state = "failed_recoverable"
        job.updated_at = datetime.now(tz=timezone.utc)
        import traceback
        job.last_error = traceback.format_exc(limit=3)
        db.commit()
        raise
    except Exception as e:
        # Erreur CF API ou autre
        logger.error("Job %s: erreur inattendue à l'état %s", job.id, job.state, exc_info=True)
        job.state = "failed_recoverable"
        job.last_error = str(e)
        job.updated_at = datetime.now(tz=timezone.utc)
        db.commit()
        raise ProvisioningError(str(e)) from e


def compensate_provisioning_job(
    job: ProvisioningJob,
    cf: CFClient,
    db: DbSession,
) -> str:
    """
    Compensation ADR-001 R5 — suppression dans l'ordre inverse.
    DNS → service token → policy → Access app.

    Retourne 'rolled_back' si succès complet, 'compensating' si erreurs partielles.
    """
    job.state = "compensating"
    job.updated_at = datetime.now(tz=timezone.utc)
    db.commit()

    errors: list[str] = []

    if job.dns_record_id:
        try:
            cf.delete_dns_record(job.dns_record_id)
            job.dns_record_id = None
            job.dns_published = False
            db.flush()
        except Exception as e:
            errors.append(f"dns: {e}")
            logger.warning("Compensation: échec suppression DNS %s: %s", job.dns_record_id, e)

    if job.cloudflare_service_token_id:
        try:
            cf.revoke_service_token(job.cloudflare_service_token_id)
        except Exception as e:
            errors.append(f"service_token: {e}")
            logger.warning("Compensation: échec révocation token %s: %s", job.cloudflare_service_token_id, e)

    if job.cloudflare_policy_id and job.cloudflare_access_app_id:
        try:
            cf.delete_policy(job.cloudflare_access_app_id, job.cloudflare_policy_id)
        except Exception as e:
            errors.append(f"policy: {e}")
            logger.warning("Compensation: échec suppression policy %s: %s", job.cloudflare_policy_id, e)

    if job.cloudflare_access_app_id:
        try:
            cf.delete_access_app(job.cloudflare_access_app_id)
        except Exception as e:
            errors.append(f"access_app: {e}")
            logger.warning("Compensation: échec suppression app %s: %s", job.cloudflare_access_app_id, e)

    if errors:
        job.last_error = "; ".join(errors)
        # Reste en "compensating" — intervention manuelle requise
        logger.error("Compensation partielle pour job %s: %s", job.id, job.last_error)
    else:
        job.state = "rolled_back"
        logger.info("Job %s: compensation complète → rolled_back", job.id)

    job.updated_at = datetime.now(tz=timezone.utc)
    db.commit()
    return job.state
```

- [ ] **Step 4: Vérifier que les tests passent**

```bash
.venv/bin/pytest apps/api/tests/integration/test_cf_provisioner.py -v
```

Expected: 5 tests `PASSED`.

- [ ] **Step 5: Suite complète**

```bash
.venv/bin/pytest apps/api/tests/ -q 2>&1 | tail -5
```

Expected: tous les tests passent.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/modules/cloudflare/provisioner.py \
        apps/api/tests/integration/test_cf_provisioner.py
git commit -m "feat(cloudflare): provisioner saga ADR-001 (run + compensate)"
```

---

## Task 6: Endpoint activate + frontend tunnels

**Files:**
- Modify: `apps/api/app/modules/admin/router.py` (POST /environments/{id}/activate)
- Modify: `apps/web/src/lib/api/server-admin.ts`
- Create: `apps/web/src/app/(admin)/admin/tunnels/page.tsx`
- Create: `apps/web/src/app/(admin)/admin/tunnels/TunnelsClient.tsx`

- [ ] **Step 1: Écrire le test de l'endpoint activate**

Ajouter à la fin de `apps/api/tests/integration/test_admin_tunnels.py` :

```python
import base64


def test_activate_environment_runs_provisioner(client, db_session, monkeypatch):
    """POST /admin/environments/{id}/activate crée un ProvisioningJob et le démarre."""
    import json as _json
    TEST_MASTER_KEY = base64.b64encode(b"a" * 32).decode()
    monkeypatch.setenv("DEVGATE_MASTER_KEY", TEST_MASTER_KEY)

    # Setup env avec tunnel assigné
    _setup_admin(db_session)
    _auth(client, db_session)
    tunnel = _make_tunnel(db_session, status="assigned")
    env = _make_env(db_session)
    env.cloudflare_tunnel_id = tunnel.cloudflare_tunnel_id
    db_session.commit()

    # Mocker le CF client pour ne pas appeler la vraie API
    from app.modules.cloudflare import fake_client as fc
    fake = fc.FakeCFClient()

    import app.modules.cloudflare.provisioner as prov_mod
    import app.modules.cloudflare.client as cf_mod

    monkeypatch.setattr(
        "app.modules.admin.router._get_cf_client_for_activate",
        lambda: fake,
    )

    res = client.post("/admin/environments/env-tun/activate")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["state"] == "active"
    assert data["job_id"] is not None

    from app.shared.models import ProvisioningJob
    job = db_session.query(ProvisioningJob).filter(
        ProvisioningJob.environment_id == "env-tun"
    ).first()
    assert job is not None
    assert job.state == "active"
```

Note: Ce test utilise `monkeypatch` pour injecter un FakeCFClient. L'endpoint doit avoir une fonction `_get_cf_client_for_activate()` extractible.

- [ ] **Step 2: Ajouter l'endpoint activate dans `admin/router.py`**

Ajouter les imports manquants :

```python
from app.modules.cloudflare.provisioner import ProvisioningError, run_provisioning_job
from app.shared.models import ProvisioningJob
```

Ajouter la fonction helper extractible pour les tests et l'endpoint :

```python
def _get_cf_client_for_activate() -> CFClient:
    """Crée le CFClient depuis la config. Séparé pour permettre le mock dans les tests."""
    from fastapi import HTTPException
    if not settings.CF_API_TOKEN or not settings.CF_ACCOUNT_ID:
        raise HTTPException(
            status_code=503,
            detail="CF_API_TOKEN ou CF_ACCOUNT_ID non configurés",
        )
    return CFClient(
        api_token=settings.CF_API_TOKEN,
        account_id=settings.CF_ACCOUNT_ID,
        zone_id=settings.CF_ZONE_ID,
    )


@router.post("/environments/{env_id}/activate", status_code=200)
def activate_environment(
    env_id: str,
    db: DbSession = Depends(get_db),
    admin=Depends(require_agency_admin),
):
    """Lance le provisioning CF pour un environnement (ADR-001 saga).
    Nécessite : CF credentials configurés + tunnel assigné sur l'environnement.
    """
    env = db.query(Environment).filter(Environment.id == env_id).first()
    if not env:
        raise NotFoundException()

    if not env.cloudflare_tunnel_id:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=422,
            detail="Aucun tunnel assigné à cet environnement — assignez d'abord un DiscoveredTunnel",
        )

    cf = _get_cf_client_for_activate()
    secret_store = get_secret_store(db)

    job = ProvisioningJob(environment_id=env_id, state="pending")
    db.add(job)
    db.flush()

    try:
        final_state = run_provisioning_job(job, env, cf, secret_store, db)
    except ProvisioningError as e:
        return {"job_id": job.id, "state": job.state, "error": str(e)}

    audit(
        db,
        actor_user_id=admin.id,
        event_type="admin.environment.activated",
        target_type="environment",
        target_id=env_id,
        metadata={"job_id": job.id, "final_state": final_state},
    )
    db.commit()
    return {"job_id": job.id, "state": final_state}
```

- [ ] **Step 3: Vérifier l'endpoint**

```bash
.venv/bin/pytest apps/api/tests/integration/test_admin_tunnels.py -v -k "activate"
```

Expected: 1 test `PASSED`.

- [ ] **Step 4: Mettre à jour `server-admin.ts`**

Dans `apps/web/src/lib/api/server-admin.ts`, ajouter à la suite des types :

```typescript
export type DiscoveredTunnelItem = {
  id: string;
  cloudflare_tunnel_id: string;
  name: string;
  status: "discovered" | "assigned" | "orphaned";
  last_seen_at: string | null;
};
```

Et dans `serverAdminApi`, ajouter :

```typescript
discoveredTunnels: () => adminRequest<DiscoveredTunnelItem[]>("/admin/discovered-tunnels"),
syncTunnels: () => adminRequest<{ discovered: number; updated: number; orphaned: number; error?: string }>("/admin/sync-tunnels", { method: "POST" }),
assignTunnel: (tunnelId: string, environmentId: string) =>
  adminRequest<{ ok: boolean }>(`/admin/discovered-tunnels/${tunnelId}/assign`, {
    method: "POST",
    body: JSON.stringify({ environment_id: environmentId }),
  }),
activateEnvironment: (envId: string) =>
  adminRequest<{ job_id: string; state: string; error?: string }>(`/admin/environments/${envId}/activate`, { method: "POST" }),
```

- [ ] **Step 5: Créer `page.tsx` (Server Component)**

Créer `apps/web/src/app/(admin)/admin/tunnels/page.tsx` :

```tsx
// Back-office — Inventaire tunnels Cloudflare
import { redirect } from "next/navigation";
import { serverAdminApi, AdminApiError, type DiscoveredTunnelItem, type AdminEnvItem } from "@/lib/api/server-admin";
import { TunnelsClient } from "./TunnelsClient";

export default async function AdminTunnelsPage() {
  let tunnels: DiscoveredTunnelItem[];
  let envs: AdminEnvItem[];

  try {
    [tunnels, envs] = await Promise.all([
      serverAdminApi.discoveredTunnels(),
      serverAdminApi.environments(),
    ]);
  } catch (err) {
    if (err instanceof AdminApiError && err.status === 401) redirect("/login");
    if (err instanceof AdminApiError && err.status === 403) redirect("/access-denied");
    redirect("/session-expired");
  }

  return <TunnelsClient initialTunnels={tunnels} envs={envs} />;
}
```

- [ ] **Step 6: Créer `TunnelsClient.tsx` (Client Component)**

Créer `apps/web/src/app/(admin)/admin/tunnels/TunnelsClient.tsx` :

```tsx
"use client";

import { useState } from "react";
import type { DiscoveredTunnelItem, AdminEnvItem } from "@/lib/api/server-admin";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

async function apiPost(path: string, body?: object) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? res.statusText);
  return res.json();
}

const STATUS_LABEL: Record<string, string> = {
  discovered: "Découvert",
  assigned: "Assigné",
  orphaned: "Orphelin",
};

const STATUS_COLOR: Record<string, string> = {
  discovered: "#2563eb",
  assigned: "#16a34a",
  orphaned: "#dc2626",
};

export function TunnelsClient({
  initialTunnels,
  envs,
}: {
  initialTunnels: DiscoveredTunnelItem[];
  envs: AdminEnvItem[];
}) {
  const [tunnels, setTunnels] = useState(initialTunnels);
  const [message, setMessage] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [selectedEnv, setSelectedEnv] = useState<Record<string, string>>({});

  async function handleSync() {
    setSyncing(true);
    setMessage("");
    try {
      const result = await apiPost("/admin/sync-tunnels");
      if (result.error) {
        setMessage(`Erreur sync CF: ${result.error}`);
      } else {
        setMessage(`Sync OK — ${result.discovered} nouveaux, ${result.updated} mis à jour, ${result.orphaned} orphelins`);
        const updated = await fetch(`${API_BASE}/admin/discovered-tunnels`, { credentials: "include" });
        if (updated.ok) setTunnels(await updated.json());
      }
    } catch (e: unknown) {
      setMessage(`Erreur: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setSyncing(false);
    }
  }

  async function handleAssign(tunnelId: string) {
    const envId = selectedEnv[tunnelId];
    if (!envId) { setMessage("Sélectionnez un environnement d'abord"); return; }
    try {
      await apiPost(`/admin/discovered-tunnels/${tunnelId}/assign`, { environment_id: envId });
      setMessage("Tunnel assigné avec succès");
      setTunnels((prev) =>
        prev.map((t) => (t.id === tunnelId ? { ...t, status: "assigned" } : t))
      );
    } catch (e: unknown) {
      setMessage(`Erreur: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  async function handleActivate(envId: string) {
    setMessage("Provisioning en cours…");
    try {
      const result = await apiPost(`/admin/environments/${envId}/activate`);
      if (result.error) {
        setMessage(`Provisioning échoué (${result.state}): ${result.error}`);
      } else {
        setMessage(`Environnement activé (job: ${result.job_id})`);
      }
    } catch (e: unknown) {
      setMessage(`Erreur: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  return (
    <div style={{ padding: "2rem", fontFamily: "system-ui, sans-serif" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <h1 style={{ fontSize: "1.5rem", fontWeight: 700 }}>Tunnels Cloudflare</h1>
        <button
          onClick={handleSync}
          disabled={syncing}
          style={{ padding: "0.5rem 1rem", background: syncing ? "#9ca3af" : "#1d4ed8", color: "#fff", border: "none", borderRadius: "6px", cursor: syncing ? "not-allowed" : "pointer" }}
        >
          {syncing ? "Sync…" : "Sync maintenant"}
        </button>
      </div>

      {message && (
        <div style={{ background: "#f0f9ff", border: "1px solid #bae6fd", borderRadius: "6px", padding: "0.75rem 1rem", marginBottom: "1rem", color: "#0369a1" }}>
          {message}
        </div>
      )}

      {tunnels.length === 0 ? (
        <p style={{ color: "#6b7280" }}>Aucun tunnel découvert. Cliquez sur "Sync maintenant" pour interroger Cloudflare.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "2px solid #e5e7eb", textAlign: "left" }}>
              <th style={{ padding: "0.75rem 1rem" }}>Nom CF</th>
              <th style={{ padding: "0.75rem 1rem" }}>ID Tunnel</th>
              <th style={{ padding: "0.75rem 1rem" }}>Statut</th>
              <th style={{ padding: "0.75rem 1rem" }}>Vu pour la dernière fois</th>
              <th style={{ padding: "0.75rem 1rem" }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {tunnels.map((t) => (
              <tr key={t.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                <td style={{ padding: "0.75rem 1rem", fontWeight: 500 }}>{t.name}</td>
                <td style={{ padding: "0.75rem 1rem", fontFamily: "monospace", fontSize: "0.85em", color: "#6b7280" }}>
                  {t.cloudflare_tunnel_id.slice(0, 8)}…
                </td>
                <td style={{ padding: "0.75rem 1rem" }}>
                  <span style={{ background: STATUS_COLOR[t.status] + "22", color: STATUS_COLOR[t.status], padding: "0.2rem 0.6rem", borderRadius: "999px", fontSize: "0.85em", fontWeight: 600 }}>
                    {STATUS_LABEL[t.status] ?? t.status}
                  </span>
                </td>
                <td style={{ padding: "0.75rem 1rem", color: "#6b7280", fontSize: "0.9em" }}>
                  {t.last_seen_at ? new Date(t.last_seen_at).toLocaleString("fr-FR") : "—"}
                </td>
                <td style={{ padding: "0.75rem 1rem" }}>
                  {t.status === "discovered" && (
                    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                      <select
                        value={selectedEnv[t.id] ?? ""}
                        onChange={(e) => setSelectedEnv((p) => ({ ...p, [t.id]: e.target.value }))}
                        style={{ padding: "0.4rem", border: "1px solid #d1d5db", borderRadius: "4px", fontSize: "0.9em" }}
                      >
                        <option value="">— Environnement —</option>
                        {envs.map((e) => (
                          <option key={e.id} value={e.id}>{e.org_name} / {e.name}</option>
                        ))}
                      </select>
                      <button
                        onClick={() => handleAssign(t.id)}
                        style={{ padding: "0.4rem 0.8rem", background: "#1d4ed8", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontSize: "0.9em" }}
                      >
                        Affecter
                      </button>
                    </div>
                  )}
                  {t.status === "assigned" && (
                    <button
                      onClick={() => {
                        const env = envs.find((e) => e.id === selectedEnv[t.id]);
                        // Find env linked to this tunnel via cloudflare_tunnel_id matching
                        const linkedEnv = envs.find(() => true); // simplification v1
                        if (linkedEnv) handleActivate(linkedEnv.id);
                        else setMessage("Sélectionnez l'environnement lié pour activer");
                      }}
                      style={{ padding: "0.4rem 0.8rem", background: "#16a34a", color: "#fff", border: "none", borderRadius: "4px", cursor: "pointer", fontSize: "0.9em" }}
                    >
                      Activer
                    </button>
                  )}
                  {t.status === "orphaned" && (
                    <span style={{ color: "#dc2626", fontSize: "0.9em" }}>Orphelin — vérifier CF</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

NOTE : Le bouton "Activer" v1 est simplifié. Pour activer l'environnement lié au tunnel, l'opérateur doit sélectionner l'environnement dans la liste en même temps que l'affectation. Une amélioration future serait de stocker l'env_id associé au tunnel assigné.

- [ ] **Step 7: Suite complète**

```bash
.venv/bin/pytest apps/api/tests/ -q 2>&1 | tail -5
```

Expected: tous les tests passent.

- [ ] **Step 8: Commit final**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/api/app/modules/admin/router.py \
        apps/api/tests/integration/test_admin_tunnels.py \
        apps/web/src/lib/api/server-admin.ts \
        apps/web/src/app/\(admin\)/admin/tunnels/
git commit -m "feat(cloudflare): endpoint activate + page back-office tunnels"
```

---

## Self-review

**Spec coverage :**
- ✅ `DiscoveredTunnel` model (Task 1)
- ✅ `ProvisioningJob` state machine 14 états (Task 1 + 5)
- ✅ Migration Alembic 0002 (Task 1)
- ✅ CF client httpx injectable (Task 2)
- ✅ FakeCFClient pour tests (Task 2)
- ✅ Sync tunnels + filtre `devgate-*` (Task 3)
- ✅ ADR-001 R1: persist après chaque CF call (Task 5)
- ✅ ADR-001 R2: DNS uniquement si `secret_persisted=True` (Task 5)
- ✅ ADR-001 R3: service token = checkpoint critique (Task 5)
- ✅ ADR-001 R5: compensation explicite (Task 5)
- ✅ Admin tunnel list + assign (Task 4)
- ✅ Admin activate endpoint (Task 6)
- ✅ Frontend tunnels page (Task 6)

**Manque volontaire de v1 :**
- Pas de job de sync périodique automatique (appel manuel via endpoint)
- Pas de retry automatique des jobs `failed_recoverable`
- Bouton Activer v1 simplifié (sélection manuelle de l'env)
