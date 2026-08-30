# Phase 7 — Hardening & Go-Live: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Renforcer la sécurité du système avant la mise en production en ajoutant le rate-limiting sur `/auth/verify`, en mettant à jour la configuration d'exemple, et en produisant un checklist de mise en production.

**Architecture:** Aucune nouvelle couche d'infrastructure — uniquement des ajouts minimaux dans les modules existants. Le rate-limiter en mémoire existant (`RateLimiter`) est réutilisé tel quel. Les fichiers `.env.example` sont enrichis avec les variables absentes (DEVGATE_MASTER_KEY, CF_ZONE_ID, COOKIE_SECURE). Le checklist go-live est un document markdown autonome.

**Tech Stack:** Python FastAPI, module `rate_limit.py` existant, markdown.

---

## Fichiers créés ou modifiés

| Fichier | Action | Responsabilité |
|---|---|---|
| `apps/api/app/modules/auth/rate_limit.py` | Modify | Ajouter `login_verify_limiter` |
| `apps/api/app/modules/auth/router.py` | Modify | Utiliser `login_verify_limiter` dans `login_verify()` |
| `apps/api/app/modules/auth/schemas.py` | Read-only | Vérifier le champ `token` de `LoginVerifyRequest` |
| `apps/api/tests/unit/test_rate_limit.py` | Modify | Tests pour `login_verify_limiter` |
| `apps/api/tests/integration/test_auth_router.py` | Modify | Test 429 sur `/auth/verify` |
| `apps/api/.env.example` | Modify | Ajouter DEVGATE_MASTER_KEY, CF_ZONE_ID, COOKIE_SECURE |
| `docs/go-live-checklist.md` | Create | Checklist de déploiement production |

---

## Task 1: Rate-limiting sur `POST /auth/verify`

**Context:** `/auth/start` est déjà rate-limité (5 req / 10 min par IP+email). `/auth/verify` ne l'est pas — un attaquant peut brute-forcer le code OTP (6 chiffres = 1 million combinaisons). On ajoute un limiter de 10 tentatives par 5 minutes par IP.

**Files:**
- Modify: `apps/api/app/modules/auth/rate_limit.py`
- Modify: `apps/api/app/modules/auth/router.py`
- Modify: `apps/api/tests/unit/test_rate_limit.py`
- Modify: `apps/api/tests/integration/test_auth_router.py`

- [ ] **Step 1: Écrire le test unitaire (failing)**

Ajouter à la fin de `apps/api/tests/unit/test_rate_limit.py` :

```python
from app.modules.auth.rate_limit import login_verify_limiter


def test_verify_limiter_blocks_at_limit():
    """login_verify_limiter bloque après 10 tentatives."""
    from app.modules.auth.rate_limit import RateLimiter, RateLimitExceeded
    limiter = RateLimiter(max_requests=10, window_seconds=300)
    for _ in range(10):
        limiter.check("1.2.3.4")
    with pytest.raises(RateLimitExceeded):
        limiter.check("1.2.3.4")


def test_verify_limiter_instance_exists():
    """login_verify_limiter est une instance RateLimiter avec les bons paramètres."""
    assert login_verify_limiter.max_requests == 10
    assert login_verify_limiter.window_seconds == 300
```

- [ ] **Step 2: Vérifier que le test échoue**

```bash
cd apps/api && python -m pytest tests/unit/test_rate_limit.py::test_verify_limiter_instance_exists -v
```

Expected: `ImportError: cannot import name 'login_verify_limiter'`

- [ ] **Step 3: Ajouter `login_verify_limiter` dans `rate_limit.py`**

Ajouter à la fin de `apps/api/app/modules/auth/rate_limit.py` (après `login_start_limiter`) :

```python
# Shared instance for /auth/verify — 10 attempts per 5 minutes
login_verify_limiter = RateLimiter(max_requests=10, window_seconds=300)
```

- [ ] **Step 4: Vérifier que les tests unitaires passent**

```bash
cd apps/api && python -m pytest tests/unit/test_rate_limit.py -v
```

Expected: tous les tests PASS.

- [ ] **Step 5: Écrire le test d'intégration (failing)**

Lire `apps/api/tests/integration/test_auth_router.py` pour trouver les helpers existants (`_make_pending_user`, etc.), puis ajouter à la fin du fichier :

```python
def test_verify_rate_limited(client, db_session, monkeypatch):
    """POST /auth/verify retourne 429 après 10 tentatives depuis la même IP."""
    from app.modules.auth import rate_limit as rl_mod
    from app.modules.auth.rate_limit import RateLimiter

    # Remplace le limiter par un limiter frais max=2 pour accélérer le test
    monkeypatch.setattr(rl_mod, "login_verify_limiter", RateLimiter(max_requests=2, window_seconds=300))

    for _ in range(2):
        client.post("/auth/verify", json={"token": "wrong-token"})

    res = client.post("/auth/verify", json={"token": "wrong-token"})
    assert res.status_code == 429
```

- [ ] **Step 6: Vérifier que le test d'intégration échoue**

```bash
cd apps/api && python -m pytest tests/integration/test_auth_router.py::test_verify_rate_limited -v
```

Expected: FAIL — le handler ne rate-limite pas encore.

- [ ] **Step 7: Brancher `login_verify_limiter` dans `router.py`**

Dans `apps/api/app/modules/auth/router.py`, modifier :

```python
# Ligne actuelle (ligne 6) :
from app.modules.auth.rate_limit import login_start_limiter

# Remplacer par :
from app.modules.auth.rate_limit import login_start_limiter, login_verify_limiter
```

Modifier la fonction `login_verify` :

```python
@router.post("/verify", response_model=LoginVerifyResponse)
def login_verify(body: LoginVerifyRequest, request: Request, response: Response, db: DbSession = Depends(get_db)):
    key = request.client.host if request.client else "unknown"
    login_verify_limiter.check(key)
    session = verify_token(body.token, db)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session.id,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=SESSION_TTL_SECONDS,
    )
    return LoginVerifyResponse(ok=True, session_created=True, redirect_to="/portal")
```

Note : ajouter `request: Request` comme paramètre (déjà importé via `from fastapi import APIRouter, Depends, Request, Response`).

- [ ] **Step 8: Vérifier que tous les tests passent**

```bash
cd apps/api && python -m pytest tests/unit/test_rate_limit.py tests/integration/test_auth_router.py -v
```

Expected: tous PASS.

- [ ] **Step 9: Lancer la suite complète**

```bash
cd apps/api && python -m pytest -q
```

Expected: tous PASS (aucune régression).

- [ ] **Step 10: Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/api/app/modules/auth/rate_limit.py \
        apps/api/app/modules/auth/router.py \
        apps/api/tests/unit/test_rate_limit.py \
        apps/api/tests/integration/test_auth_router.py
git commit -m "feat(auth): rate-limit POST /auth/verify (10 req / 5 min par IP)"
```

---

## Task 2: Mise à jour des fichiers `.env.example`

**Context:** `apps/api/.env.example` ne documente pas `DEVGATE_MASTER_KEY` (requis pour le secret store) ni `CF_ZONE_ID` (requis pour la provisioning CF — Plan A). `COOKIE_SECURE` n'est pas documenté comme devant être `true` en prod.

**Files:**
- Modify: `apps/api/.env.example`

- [ ] **Step 1: Vérifier le contenu actuel**

```bash
cat apps/api/.env.example
```

Expected : le fichier liste les variables existantes mais il manque `DEVGATE_MASTER_KEY`, `CF_ZONE_ID`, et `COOKIE_SECURE`.

- [ ] **Step 2: Mettre à jour `apps/api/.env.example`**

Remplacer le contenu intégral par :

```dotenv
# DevGate API — variables d'environnement
# Copier en .env et adapter

ENV=development
DEBUG=true

# PostgreSQL
DATABASE_URL=postgresql+psycopg://devgate:devgate@localhost:5432/devgate

# Session
SESSION_SECRET_KEY=changeme-generate-a-real-secret
SESSION_TTL_DAYS=7

# Cookie — mettre à true en production (HTTPS obligatoire)
COOKIE_SECURE=false

# Email provider
# - fake   : stocke en mémoire (tests / dev)
# - smtp   : envoi SMTP (Mailpit en dev, MTA en prod)
# - resend : API Resend (non implémenté en v1)
EMAIL_PROVIDER=smtp

# SMTP (dev : Mailpit sur localhost:1025)
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_FROM=DevGate <no-reply@devgate.local>

# Resend (production)
RESEND_API_KEY=re_xxx

# Frontend URL (pour construire les magic links)
FRONTEND_BASE_URL=http://localhost:3000

# Secret store — OBLIGATOIRE en production
# Générer : python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
# NE JAMAIS COMMITER cette valeur. Stocker dans 1Password / Vault / Doppler.
DEVGATE_MASTER_KEY=

# Cloudflare — OBLIGATOIRE pour l'intégration tunnels (Phase 6)
# Jamais exposé au frontend. Stocker dans un gestionnaire de secrets.
CF_API_TOKEN=
CF_ACCOUNT_ID=
CF_ZONE_ID=
```

- [ ] **Step 3: Vérifier**

```bash
cat apps/api/.env.example
```

Expected : toutes les variables présentes avec commentaires.

- [ ] **Step 4: Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add apps/api/.env.example
git commit -m "docs: env.example — ajouter DEVGATE_MASTER_KEY, CF_ZONE_ID, COOKIE_SECURE"
```

---

## Task 3: Checklist de mise en production

**Context:** Avant de pousser DevGate sur un vrai serveur, l'équipe doit vérifier un ensemble de points critiques. Ce document centralise le checklist. Il n'y a rien de code à produire — uniquement un document markdown.

**Files:**
- Create: `docs/go-live-checklist.md`

- [ ] **Step 1: Créer `docs/go-live-checklist.md`**

```markdown
# DevGate — Checklist Go-Live

Document de référence avant chaque déploiement en production.

## Infrastructure

- [ ] PostgreSQL accessible depuis le backend (connection pool configuré)
- [ ] Migrations Alembic à jour : `alembic upgrade head` sans erreur
- [ ] Domaine principal configuré (DNS → serveur / load balancer)
- [ ] HTTPS actif sur le domaine principal (certificat TLS valide)
- [ ] `COOKIE_SECURE=true` dans la configuration production

## Secrets

- [ ] `DEVGATE_MASTER_KEY` généré et stocké hors repo (1Password / Vault / Doppler)
  - Générer : `python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"`
- [ ] `SESSION_SECRET_KEY` changé (valeur unique, longue, aléatoire)
- [ ] `CF_API_TOKEN` restreint aux permissions minimales (List/Create tunnels, Access, DNS)
- [ ] Aucune variable secrète dans les logs, les headers HTTP, ou les réponses API

## Cloudflare

- [ ] `CF_ACCOUNT_ID` et `CF_ZONE_ID` corrects (vérifier dans le dashboard CF)
- [ ] `CF_API_TOKEN` valide — tester avec `curl -H "Authorization: Bearer $CF_API_TOKEN" https://api.cloudflare.com/client/v4/user/tokens/verify`
- [ ] Au moins un tunnel `cfargotunnel.com` visible dans le dashboard CF avant la première sync

## Email

- [ ] Provider email configuré (`EMAIL_PROVIDER=smtp` ou `resend`)
- [ ] Test d'envoi effectué (magic link reçu sur une adresse réelle)
- [ ] `SMTP_FROM` ou adresse Resend vérifiée (pas de spam / rebond)

## Application

- [ ] `ENV=production` et `DEBUG=false`
- [ ] `FRONTEND_BASE_URL` pointe vers le domaine public (pas localhost)
- [ ] Tests backend passent intégralement : `pytest -q` → 0 failures
- [ ] Au moins un utilisateur admin (`kind="agency"`) créé en base
- [ ] Audit log vérifié : les événements `gateway.resource.accessed` apparaissent

## Sécurité minimale

- [ ] Rate-limiting actif sur `/auth/start` et `/auth/verify`
- [ ] Cookies `httponly=true`, `secure=true`, `samesite=lax`
- [ ] En-têtes de sécurité HTTP vérifiés (Content-Security-Policy, X-Frame-Options…)
- [ ] Logs sans données personnelles (emails, tokens, secrets)

## Opérations

- [ ] Monitoring en place (uptime, erreurs 5xx)
- [ ] Backup PostgreSQL configuré (snapshot quotidien minimum)
- [ ] Procédure de rollback documentée (restaurer snapshot + redéployer version précédente)
```

- [ ] **Step 2: Vérifier que le fichier existe**

```bash
ls -la docs/go-live-checklist.md
```

Expected : fichier créé.

- [ ] **Step 3: Commit**

```bash
cd /Users/amiellavon/Sites/Captive-serveur
git add docs/go-live-checklist.md
git commit -m "docs: checklist go-live production (secrets, CF, email, sécurité)"
```

---

## Self-Review

### Spec coverage
- ✅ Rate-limiting `/auth/verify` (Task 1)
- ✅ `.env.example` à jour avec toutes les variables v1 (Task 2)
- ✅ Checklist go-live (Task 3)

### Points hors-scope confirmés (YAGNI)
- OTP max attempts par session : le rate-limit IP suffit pour v1
- Redis pour le rate-limiter : non requis en v1 monolithe single-instance
- En-têtes HTTP de sécurité (CSP, etc.) : checklist les mentionne, implémentation future

### Dépendances inter-plans
- Plan A (CF integration) doit être mergé avant le go-live — le checklist CF de Task 3 le suppose
- `DEVGATE_MASTER_KEY` est déjà utilisé dans le secret store (Phase 5 complétée) — `.env.example` le documente seulement
