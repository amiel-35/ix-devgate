# Security Hardening — Config, Gateway & Backend

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corriger les failles de configuration, le fallback silencieux du gateway WebSocket, les fuites d'erreurs Cloudflare, et ajouter les security headers HTTP backend.

**Architecture:** Corrections dans `config.py`, `main.py`, `gateway/router.py`, `admin/router.py`, `cloudflare/provisioner.py`, `cloudflare/sync.py`. Toutes les validations de config se font au démarrage via lifespan FastAPI. Security headers via un middleware Starlette.

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy · pytest  
**Tests :** `cd apps/api && .venv/bin/python -m pytest`

---

## Fichiers modifiés

| Fichier | Action | Finding |
|---|---|---|
| `apps/api/app/config.py` | Modify | M-01, M-02, M-03, M-04 |
| `apps/api/app/main.py` | Modify | M-02, M-03, M-04, M-06 |
| `apps/api/app/modules/gateway/router.py` | Modify | C-02 |
| `apps/api/app/modules/admin/router.py` | Modify | H-05 |
| `apps/api/app/modules/cloudflare/provisioner.py` | Modify | M-07 |
| `apps/api/app/modules/cloudflare/sync.py` | Modify | H-05 |
| `apps/api/tests/integration/test_gateway.py` | Modify | C-02 |
| `apps/api/tests/integration/test_admin_router.py` | Modify | H-05 |

---

## Task 1 — C-02 : Gateway WebSocket — fail-fast si master key absente avec service_token_ref

**Finding :** Si `DEVGATE_MASTER_KEY` est absente, le WebSocket continue sans injecter les credentials CF Access.

**Files:**
- Modify: `apps/api/app/modules/gateway/router.py`
- Test: `apps/api/tests/integration/test_gateway.py`

- [ ] **Step 1 : Lire le code actuel du gateway WebSocket**

```bash
grep -n "secret_store\|DEVGATE_MASTER_KEY\|service_token_ref" apps/api/app/modules/gateway/router.py | head -30
```

Repère les lignes où `secret_store` est récupéré (souvent dans un bloc `try/except RuntimeError`).

- [ ] **Step 2 : Écrire le test qui échoue**

Dans `apps/api/tests/integration/test_gateway.py`, ajoute à la fin :

```python
def test_ws_gateway_closes_if_secret_store_unavailable_and_token_configured(
    client, db_session
):
    """
    Si l'env a un service_token_ref mais que le secret store est indisponible,
    le WebSocket doit être fermé avec code 1011, pas continuer sans credentials CF.
    """
    from app.shared.models import (
        Organization, Project, Environment, User,
        Session as DevSession, AccessGrant,
    )
    import uuid, datetime

    org = Organization(id=str(uuid.uuid4()), name="WS Test Org", slug="ws-test-org")
    project = Project(
        id=str(uuid.uuid4()), name="WS Project", slug="ws-project",
        organization_id=org.id, status="active",
    )
    env = Environment(
        id=str(uuid.uuid4()), name="WS Env", slug="ws-env",
        project_id=project.id, upstream_url="http://localhost:9999",
        service_token_ref="sec_fake_ref",  # token configuré
    )
    user = User(
        id=str(uuid.uuid4()), email="ws-test@example.com",
        kind="client", status="active",
    )
    grant = AccessGrant(
        id=str(uuid.uuid4()), user_id=user.id,
        organization_id=org.id, role="member", revoked_at=None,
    )
    session = DevSession(
        id=str(uuid.uuid4()), user_id=user.id,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=7),
    )
    for obj in [org, project, env, user, grant, session]:
        db_session.add(obj)
    db_session.commit()

    # Simuler l'absence de DEVGATE_MASTER_KEY en patchant get_secret_store
    from unittest.mock import patch
    with patch(
        "app.modules.gateway.router.get_secret_store",
        side_effect=RuntimeError("DEVGATE_MASTER_KEY manquante"),
    ):
        with client.websocket_connect(
            f"/gateway/ws/{env.slug}",
            cookies={"devgate_session": session.id},
        ) as ws:
            # Le serveur doit fermer avec un code d'erreur
            import pytest
            with pytest.raises(Exception):
                ws.receive_text()
```

Note : si le slug de l'env dans la route est différent (ex: `env_id`), adapter en conséquence.

- [ ] **Step 3 : Vérifier que le test échoue ou est skippé**

```bash
cd apps/api && .venv/bin/python -m pytest tests/integration/test_gateway.py::test_ws_gateway_closes_if_secret_store_unavailable_and_token_configured -v
```

- [ ] **Step 4 : Corriger le handler WebSocket**

Dans `apps/api/app/modules/gateway/router.py`, trouve le bloc qui récupère `secret_store`. Remplace le fallback silencieux par un fail-fast conditionnel :

```python
# AVANT (pattern à remplacer) :
try:
    secret_store = get_secret_store(db)
except RuntimeError:
    secret_store = None  # fallback silencieux

# APRÈS :
try:
    secret_store = get_secret_store(db)
except RuntimeError:
    secret_store = None

# Vérifier APRÈS la résolution de l'environnement (env est disponible ici)
# Si l'env requiert un service token CF mais que le store est indisponible : fermer
```

Le check doit se faire après que `env` est résolu. Ajoute après la résolution de l'environnement :

```python
if env.service_token_ref and secret_store is None:
    await websocket.close(code=1011)
    return
```

Si la résolution de `env` intervient après la récupération de `secret_store`, réorganise pour que la vérification se fasse à l'endroit logique (après les deux).

- [ ] **Step 5 : Vérifier que le test passe**

```bash
cd apps/api && .venv/bin/python -m pytest tests/integration/test_gateway.py::test_ws_gateway_closes_if_secret_store_unavailable_and_token_configured -v
```

- [ ] **Step 6 : Vérifier que tous les tests passent**

```bash
cd apps/api && .venv/bin/python -m pytest -x -q
```

- [ ] **Step 7 : Commit**

```bash
git add apps/api/app/modules/gateway/router.py apps/api/tests/integration/test_gateway.py
git commit -m "fix(gateway): fermer le WS si service_token_ref configuré mais master key absente (C-02)"
```

---

## Task 2 — M-01 à M-04 : Validations de configuration au démarrage

**Findings :** `COOKIE_SECURE=False` par défaut, CORS hardcodé, `DEVGATE_MASTER_KEY` sans validation, `SESSION_SECRET_KEY` avec valeur par défaut.

**Files:**
- Modify: `apps/api/app/config.py`
- Modify: `apps/api/app/main.py`

- [ ] **Step 1 : Lire `config.py` et `main.py` en entier**

```bash
cat apps/api/app/config.py
cat apps/api/app/main.py
```

- [ ] **Step 2 : Mettre à jour `config.py`**

Dans `apps/api/app/config.py`, apporte ces modifications :

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENV: str = "development"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql+psycopg://devgate:devgate@localhost:5432/devgate"

    SESSION_SECRET_KEY: str = "changeme"
    SESSION_TTL_DAYS: int = 7

    COOKIE_SECURE: bool = True  # True par défaut — mettre False en dev local explicitement

    EMAIL_PROVIDER: str = "fake"
    RESEND_API_KEY: str = ""

    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_FROM: str = "DevGate <no-reply@devgate.local>"
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    FRONTEND_BASE_URL: str = "http://localhost:3000"

    # CORS — liste configurable pour la production
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
    ]

    # Cloudflare — jamais exposé vers le frontend
    CF_API_TOKEN: str = ""
    CF_ACCOUNT_ID: str = ""
    CF_ZONE_ID: str = ""

    # Secret store — OBLIGATOIRE en production
    DEVGATE_MASTER_KEY: str = ""


settings = Settings()
```

Note : `DEVGATE_MASTER_KEY` est ajoutée ici pour la validation Pydantic au démarrage — elle était auparavant lue via `os.environ.get()` dans `deps.py`. Vérifie que `deps.py` utilise toujours `os.environ.get()` ou adapte-le pour utiliser `settings.DEVGATE_MASTER_KEY`.

- [ ] **Step 3 : Ajouter les validations au démarrage dans `main.py`**

Dans `apps/api/app/main.py`, ajoute un lifespan FastAPI avec les validations de sécurité. Trouve l'endroit où `app = FastAPI(...)` est créé et modifie :

```python
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validations de sécurité au démarrage
    if settings.ENV == "production":
        if settings.SESSION_SECRET_KEY in ("changeme", "changeme-generate-a-real-secret", ""):
            raise RuntimeError(
                "SESSION_SECRET_KEY doit être remplacée par une valeur aléatoire en production"
            )
        if not settings.DEVGATE_MASTER_KEY:
            raise RuntimeError(
                "DEVGATE_MASTER_KEY est obligatoire en production"
            )
        if not settings.COOKIE_SECURE:
            raise RuntimeError(
                "COOKIE_SECURE doit être True en production (HTTPS requis)"
            )
    elif not settings.DEVGATE_MASTER_KEY:
        logger.warning(
            "DEVGATE_MASTER_KEY non configurée — le secret store sera indisponible"
        )
    yield


app = FastAPI(lifespan=lifespan, ...)
```

Si `app = FastAPI(...)` existe déjà sans `lifespan`, ajoute `lifespan=lifespan` comme paramètre. Si une lifespan existe déjà, intègre les validations au début.

- [ ] **Step 4 : Remplacer le CORS hardcodé par `settings.ALLOWED_ORIGINS`**

Dans `apps/api/app/main.py`, trouve le bloc `CORSMiddleware` et remplace les origines hardcodées :

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Cookie"],
)
```

Note : remplacer `allow_methods=["*"]` et `allow_headers=["*"]` si présents.

- [ ] **Step 5 : Mettre à jour `.env` et `.env.example`**

Dans `apps/api/.env` (dev local), ajoute si absent :

```bash
COOKIE_SECURE=false
```

Dans `apps/api/.env.example`, ajoute/met à jour :

```bash
# Mettre false uniquement en développement local (HTTP)
COOKIE_SECURE=false

# CORS — séparer par virgule pour plusieurs origines
# ALLOWED_ORIGINS=["http://localhost:3000","https://app.mondomaine.fr"]
```

- [ ] **Step 6 : Vérifier que tous les tests passent**

```bash
cd apps/api && .venv/bin/python -m pytest -x -q
```

Si des tests échouent à cause de la valeur `COOKIE_SECURE=True` par défaut, vérifie que le `.env` de test a bien `COOKIE_SECURE=false`.

- [ ] **Step 7 : Commit**

```bash
git add apps/api/app/config.py apps/api/app/main.py apps/api/.env.example
git commit -m "fix(config): COOKIE_SECURE=True par défaut, CORS configurable, validations démarrage prod (M-01 à M-04)"
```

---

## Task 3 — M-06 : Security Headers HTTP middleware (backend)

**Finding :** Aucun header de sécurité HTTP configuré côté backend.

**Files:**
- Modify: `apps/api/app/main.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Dans `apps/api/tests/integration/test_auth.py` (ou créer `test_security_headers.py`), ajoute :

```python
def test_security_headers_present(client):
    """Les réponses API doivent inclure les security headers."""
    resp = client.get("/health")  # ou tout endpoint public
    # Si /health n'existe pas, utiliser /auth/start avec une méthode GET ou OPTIONS
    # ou appeler /docs si disponible
    assert "x-content-type-options" in resp.headers, "X-Content-Type-Options manquant"
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert "x-frame-options" in resp.headers, "X-Frame-Options manquant"
    assert resp.headers["x-frame-options"] == "DENY"
```

Si `/health` n'existe pas, utilise un endpoint qui retourne 200 (ex: `GET /docs` si `DEBUG=True`). Sinon, crée d'abord un healthcheck :

```python
# Dans apps/api/app/main.py, ajoute si absent
@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 2 : Vérifier que le test échoue**

```bash
cd apps/api && .venv/bin/python -m pytest tests/integration/test_auth.py::test_security_headers_present -v
```

Expected : FAIL — headers absents.

- [ ] **Step 3 : Ajouter le middleware Security Headers dans `main.py`**

Dans `apps/api/app/main.py`, ajoute avant les autres middlewares :

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # HSTS : uniquement en production (HTTPS requis)
        if settings.COOKIE_SECURE:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains"
            )
        return response


app.add_middleware(SecurityHeadersMiddleware)
```

Ajoute ce bloc après la création de `app` et avant les routes.

- [ ] **Step 4 : Vérifier que le test passe**

```bash
cd apps/api && .venv/bin/python -m pytest tests/integration/test_auth.py::test_security_headers_present -v
```

Expected : PASS

- [ ] **Step 5 : Vérifier que tous les tests passent**

```bash
cd apps/api && .venv/bin/python -m pytest -x -q
```

- [ ] **Step 6 : Commit**

```bash
git add apps/api/app/main.py apps/api/tests/integration/test_auth.py
git commit -m "fix(api): security headers HTTP middleware (X-Content-Type-Options, X-Frame-Options, HSTS) (M-06)"
```

---

## Task 4 — H-05 & M-07 : Ne pas exposer les erreurs Cloudflare dans les réponses HTTP

**Findings :** `str(e)` de l'API CF retourné brut dans les réponses admin. Stack traces en base.

**Files:**
- Modify: `apps/api/app/modules/admin/router.py`
- Modify: `apps/api/app/modules/cloudflare/provisioner.py`
- Modify: `apps/api/app/modules/cloudflare/sync.py`

- [ ] **Step 1 : Lire les fichiers concernés**

```bash
grep -n "str(e)\|last_error\|traceback\|format_exc" \
  apps/api/app/modules/admin/router.py \
  apps/api/app/modules/cloudflare/provisioner.py \
  apps/api/app/modules/cloudflare/sync.py
```

- [ ] **Step 2 : Écrire le test qui échoue**

Dans `apps/api/tests/integration/test_admin_router.py`, ajoute :

```python
def test_activate_error_does_not_leak_cf_details(client_admin, db_session, monkeypatch):
    """En cas d'erreur de provisioning, la réponse ne doit pas contenir str(e) de l'API CF."""
    from app.modules.cloudflare.provisioner import ProvisioningError

    def fail_provision(*args, **kwargs):
        raise ProvisioningError("CF internal error: token=secret123 account=acc456")

    monkeypatch.setattr(
        "app.modules.cloudflare.provisioner.CloudflareProvisioner.run",
        fail_provision,
    )

    # Créer un env et tenter l'activation (adapter selon les fixtures existantes)
    # ... setup minimal d'un environnement ...
    # resp = client_admin.post(f"/admin/environments/{env_id}/activate")
    # assert "secret123" not in resp.text
    # assert "acc456" not in resp.text
    # assert "CF internal error" not in resp.text
    pass  # Implémenter selon les fixtures disponibles dans le projet
```

Note : Si le test est complexe à écrire en isolation, fait une vérification manuelle du code à la place et commite la correction directement.

- [ ] **Step 3 : Corriger `admin/router.py` — masquer les erreurs CF**

Dans `apps/api/app/modules/admin/router.py`, trouve les endroits où `str(e)` ou `error=str(e)` apparaît dans les réponses. Remplace par :

```python
import logging
logger = logging.getLogger(__name__)

# Dans le handler activate/provision :
except ProvisioningError as e:
    logger.error("Provisioning failed for env %s: %s", env_id, str(e))
    return {
        "job_id": job.id if job else None,
        "state": "failed_recoverable",
        "error": "Provisioning échoué — consultez les logs serveur pour les détails",
    }
```

- [ ] **Step 4 : Corriger `provisioner.py` — ne pas stocker la stack trace**

Dans `apps/api/app/modules/cloudflare/provisioner.py`, trouve où `traceback.format_exc()` ou `str(e)` est stocké dans `job.last_error`. Remplace :

```python
# AVANT
job.last_error = traceback.format_exc()

# APRÈS
logger.error("Provisioning error for job %s: %s", job.id, traceback.format_exc())
job.last_error = str(e)  # Message d'erreur sans stack trace
```

Si `logger` n'est pas importé dans ce fichier :

```python
import logging
logger = logging.getLogger(__name__)
```

- [ ] **Step 5 : Corriger `sync.py` — masquer les erreurs CF**

Dans `apps/api/app/modules/cloudflare/sync.py`, trouve `{"error": str(e), ...}` et remplace :

```python
except Exception as e:
    logger.error("CF sync error: %s", str(e))
    return {"error": "Synchronisation CF échouée — consultez les logs serveur", "synced": 0}
```

- [ ] **Step 6 : Vérifier que tous les tests passent**

```bash
cd apps/api && .venv/bin/python -m pytest -x -q
```

- [ ] **Step 7 : Commit**

```bash
git add apps/api/app/modules/admin/router.py \
        apps/api/app/modules/cloudflare/provisioner.py \
        apps/api/app/modules/cloudflare/sync.py
git commit -m "fix(cloudflare): masquer les erreurs CF dans les réponses HTTP, logger côté serveur (H-05, M-07)"
```

---

## Self-Review

### Spec coverage
- ✅ C-02 — WebSocket fail-fast si master key absente
- ✅ M-01 — COOKIE_SECURE=True par défaut
- ✅ M-02 — CORS configurable via ALLOWED_ORIGINS
- ✅ M-03 — DEVGATE_MASTER_KEY validée au démarrage
- ✅ M-04 — SESSION_SECRET_KEY validée au démarrage
- ✅ M-06 — Security headers middleware backend
- ✅ H-05 — Erreurs CF masquées dans les réponses
- ✅ M-07 — Stack traces logguées côté serveur uniquement

### Points hors scope
- M-06 frontend (Next.js headers) — Plan C
- H-04 (Docker deps) — Plan C
- M-08 (dépendances épinglées) — Plan C
