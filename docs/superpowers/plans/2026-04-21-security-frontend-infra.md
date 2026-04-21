# Security Hardening — Frontend, Infrastructure & Misc

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sécuriser le frontend Next.js (headers, layout admin), séparer les dépendances dev/prod dans Docker, épingler les dépendances critiques, et ajouter les corrections mineures restantes.

**Architecture:** Corrections dans `next.config.ts`, `(admin)/layout.tsx`, `Dockerfile`, `requirements.txt` / `pyproject.toml`, `gateway/router.py`, `secrets/store.py`. Pas de breaking changes dans les flux métier.

**Tech Stack:** Next.js TypeScript · Python 3.11 · Docker · FastAPI  
**Tests Python :** `cd apps/api && .venv/bin/python -m pytest`

---

## Fichiers modifiés

| Fichier | Action | Finding |
|---|---|---|
| `apps/web/next.config.ts` | Modify | M-06 frontend |
| `apps/web/src/app/(admin)/layout.tsx` | Modify | M-05 |
| `apps/api/Dockerfile` | Modify | H-04 |
| `apps/api/requirements.txt` ou `pyproject.toml` | Modify | M-08 |
| `apps/api/app/modules/gateway/router.py` | Modify | F-05 |
| `apps/api/app/modules/secrets/store.py` | Modify | F-06 |

---

## Task 1 — M-06 : Security Headers Next.js

**Finding :** Aucun header de sécurité configuré dans Next.js (X-Frame-Options, nosniff, Referrer-Policy, CSP).

**Files:**
- Modify: `apps/web/next.config.ts`

- [ ] **Step 1 : Lire la config Next.js actuelle**

```bash
cat apps/web/next.config.ts
```

- [ ] **Step 2 : Ajouter les security headers**

Dans `apps/web/next.config.ts`, ajoute une fonction `headers` dans la config :

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // ... config existante ...

  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          {
            // CSP de base — affiner selon les sources réelles (fonts, images, etc.)
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval'", // unsafe-* requis par Next.js dev
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: blob:",
              "frame-ancestors 'none'",
            ].join("; "),
          },
        ],
      },
    ];
  },
};

export default nextConfig;
```

Note : `unsafe-inline` et `unsafe-eval` dans `script-src` sont nécessaires pour Next.js en développement. En production, Next.js supporte les nonces CSP — documenté comme amélioration future.

- [ ] **Step 3 : Vérifier que le build Next.js compile**

```bash
cd apps/web && npm run build 2>&1 | tail -20
```

Expected : build réussi, pas d'erreur de config.

- [ ] **Step 4 : Vérifier manuellement les headers en dev**

```bash
cd apps/web && npm run dev &
sleep 3
curl -I http://localhost:3001 2>/dev/null | grep -iE "x-frame|x-content|referrer|permissions|content-security"
kill %1
```

Expected : les headers apparaissent dans la réponse.

- [ ] **Step 5 : Commit**

```bash
git add apps/web/next.config.ts
git commit -m "fix(web): security headers Next.js (X-Frame-Options, CSP, Referrer-Policy) (M-06)"
```

---

## Task 2 — M-05 : Admin layout — rediriger sur toute erreur non gérée

**Finding :** En cas d'erreur 500 ou timeout sur `/admin/stats`, l'utilisateur accède au layout admin sans vérification de rôle.

**Files:**
- Modify: `apps/web/src/app/(admin)/layout.tsx`

- [ ] **Step 1 : Lire le layout actuel**

```bash
cat "apps/web/src/app/(admin)/layout.tsx"
```

- [ ] **Step 2 : Corriger la gestion d'erreur**

Dans `apps/web/src/app/(admin)/layout.tsx`, trouve le bloc `try/catch` qui appelle `serverAdminApi.stats()` (ou l'équivalent).

Remplace le comportement "laisser passer en cas d'erreur inconnue" par une redirection vers `/login` :

```typescript
try {
    await serverAdminApi.stats();
} catch (err) {
    if (err instanceof AdminApiError && err.status === 403) {
        redirect("/access-denied");
    }
    // Tout autre cas (401, 500, timeout réseau, erreur inconnue) :
    // refuser l'accès plutôt que de laisser passer
    redirect("/login");
}
```

Si `AdminApiError` n'est pas importé dans ce fichier, vérifie les imports existants et utilise la classe d'erreur correcte.

- [ ] **Step 3 : Vérifier que le build compile**

```bash
cd apps/web && npm run build 2>&1 | grep -E "error|Error|warning" | head -20
```

Expected : aucune erreur TypeScript.

- [ ] **Step 4 : Commit**

```bash
git add "apps/web/src/app/(admin)/layout.tsx"
git commit -m "fix(web): admin layout redirige vers /login sur toute erreur non gérée (M-05)"
```

---

## Task 3 — H-04 : Séparer les dépendances dev/prod dans le Dockerfile

**Finding :** `pytest`, `mypy`, `ruff`, `respx` installés dans l'image de production.

**Files:**
- Modify: `apps/api/Dockerfile`
- Create: `apps/api/requirements-prod.txt` (si `requirements.txt` contient les deps dev)

- [ ] **Step 1 : Inspecter le Dockerfile et requirements actuels**

```bash
cat apps/api/Dockerfile
cat apps/api/requirements.txt
# Vérifier si pyproject.toml sépare dev/prod
grep -A 10 "optional-dependencies\|dev\s*=" apps/api/pyproject.toml
```

- [ ] **Step 2 : Créer `requirements-prod.txt` sans les deps dev**

Si `requirements.txt` contient `pytest`, `mypy`, `ruff`, `respx` ou `pytest-asyncio`, crée un fichier séparé :

```bash
# Lire les deps actuelles et identifier les deps de prod uniquement
# Les deps de dev typiques : pytest, pytest-asyncio, pytest-cov, ruff, mypy, respx, httpx (si uniquement pour tests)
```

Crée `apps/api/requirements-prod.txt` avec uniquement les dépendances nécessaires en production (exclure tout ce qui commence par `pytest`, `ruff`, `mypy`, `respx`) :

```
# apps/api/requirements-prod.txt
# Dépendances de production uniquement — généré manuellement depuis requirements.txt
fastapi>=0.115
uvicorn[standard]>=0.30
sqlalchemy>=2.0
alembic>=1.13
pydantic>=2.0
pydantic-settings>=2.0
httpx>=0.27
cryptography>=42
psycopg[binary]>=3.1
itsdangerous>=2.1
python-multipart>=0.0.9
```

Adapte la liste selon le contenu réel de `requirements.txt`. Ne pas inclure : `pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`, `respx`.

- [ ] **Step 3 : Modifier le Dockerfile pour utiliser `requirements-prod.txt`**

Dans `apps/api/Dockerfile`, remplace la ligne d'installation des dépendances :

```dockerfile
# AVANT
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# APRÈS
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt
```

Si le Dockerfile utilise `pyproject.toml` avec `pip install -e .`, assure-toi que les extras de dev ne sont pas installés :

```dockerfile
# Installer sans les extras dev
RUN pip install --no-cache-dir . --no-deps
RUN pip install --no-cache-dir $(python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); print(' '.join(d['project']['dependencies']))")
```

Ou plus simplement avec `pip install --no-cache-dir .` (sans `[dev]`).

- [ ] **Step 4 : Vérifier que le build Docker fonctionne**

```bash
cd apps/api && docker build -t devgate-api-test . 2>&1 | tail -20
```

Expected : build réussi.

- [ ] **Step 5 : Vérifier que pytest n'est pas dans l'image**

```bash
docker run --rm devgate-api-test python -c "import pytest" 2>&1
```

Expected : `ModuleNotFoundError: No module named 'pytest'`

- [ ] **Step 6 : Commit**

```bash
git add apps/api/Dockerfile apps/api/requirements-prod.txt
git commit -m "fix(docker): séparer les dépendances dev/prod, exclure pytest/mypy/ruff de l'image prod (H-04)"
```

---

## Task 4 — M-08 : Épingler les dépendances critiques

**Finding :** Toutes les dépendances utilisent `>=` sans borne supérieure — builds non reproductibles.

**Files:**
- Modify: `apps/api/requirements.txt` ou `apps/api/pyproject.toml`

- [ ] **Step 1 : Générer les versions actuellement installées**

```bash
cd apps/api && .venv/bin/pip freeze | grep -E "fastapi|sqlalchemy|cryptography|alembic|httpx|pydantic|uvicorn|psycopg|itsdangerous"
```

- [ ] **Step 2 : Épingler les dépendances critiques dans `requirements.txt`**

Dans `apps/api/requirements.txt`, remplace les contraintes `>=` des dépendances critiques de sécurité par des contraintes de version mineure (`~=` ou `>=x.y,<x+1`) :

```
# Dépendances critiques — épinglées à la version mineure
cryptography>=44.0,<45     # Chiffrement AES-GCM — ne pas upgrader automatiquement
fastapi>=0.115,<1.0        # API framework
sqlalchemy>=2.0,<3.0       # ORM
httpx>=0.27,<1.0           # Client HTTP gateway
pydantic>=2.0,<3.0         # Validation
alembic>=1.13,<2.0         # Migrations
```

Note : utilise les versions réellement installées dans `.venv` (étape 1) comme référence, pas ces valeurs.

- [ ] **Step 3 : Vérifier que les tests passent avec les versions épinglées**

```bash
cd apps/api && .venv/bin/python -m pytest -x -q
```

- [ ] **Step 4 : Commit**

```bash
git add apps/api/requirements.txt
git commit -m "fix(deps): épingler les dépendances critiques à la version mineure (M-08)"
```

---

## Task 5 — F-05 : Validation UUID sur les paramètres de route

**Finding :** Les `env_id` et autres IDs dans les routes gateway/admin sont des `str` sans validation de format UUID.

**Files:**
- Modify: `apps/api/app/modules/gateway/router.py`
- Modify: `apps/api/app/modules/admin/router.py`

- [ ] **Step 1 : Identifier les routes concernées**

```bash
grep -n "env_id\|environment_id\|org_id\|user_id" \
  apps/api/app/modules/gateway/router.py \
  apps/api/app/modules/admin/router.py | grep "str" | head -20
```

- [ ] **Step 2 : Écrire le test qui échoue**

Dans `apps/api/tests/integration/test_admin_router.py`, ajoute :

```python
def test_invalid_uuid_env_id_returns_422(client_admin):
    """Un env_id non-UUID doit retourner 422, pas 500 ou 404 avec un message d'erreur SQL."""
    resp = client_admin.post("/admin/environments/not-a-uuid/activate")
    assert resp.status_code == 422, (
        f"Un env_id non-UUID doit retourner 422, got {resp.status_code}: {resp.text[:200]}"
    )
```

- [ ] **Step 3 : Vérifier que le test échoue**

```bash
cd apps/api && .venv/bin/python -m pytest tests/integration/test_admin_router.py::test_invalid_uuid_env_id_returns_422 -v
```

Expected : FAIL (retourne 404 ou 500 au lieu de 422)

- [ ] **Step 4 : Remplacer `str` par `UUID` dans les paramètres de route**

Dans `apps/api/app/modules/gateway/router.py` et `apps/api/app/modules/admin/router.py`, remplace les paramètres `env_id: str` par `env_id: UUID` dans les signatures de route :

```python
from uuid import UUID

# AVANT
@router.post("/environments/{env_id}/activate")
def activate_environment(env_id: str, ...):

# APRÈS
@router.post("/environments/{env_id}/activate")
def activate_environment(env_id: UUID, ...):
    env_id_str = str(env_id)  # Convertir pour les queries SQLAlchemy si nécessaire
```

Applique le même changement à tous les paramètres `_id: str` dans les routes qui correspondent à des UUIDs en base.

Note : si les IDs en base sont stockés comme `str` (UUID sans tirets ou avec), assure-toi de la conversion correcte.

- [ ] **Step 5 : Vérifier que le test passe**

```bash
cd apps/api && .venv/bin/python -m pytest tests/integration/test_admin_router.py::test_invalid_uuid_env_id_returns_422 -v
```

Expected : PASS

- [ ] **Step 6 : Vérifier que tous les tests passent**

```bash
cd apps/api && .venv/bin/python -m pytest -x -q
```

- [ ] **Step 7 : Commit**

```bash
git add apps/api/app/modules/gateway/router.py apps/api/app/modules/admin/router.py \
        apps/api/tests/integration/test_admin_router.py
git commit -m "fix(api): validation UUID sur les paramètres de route (F-05)"
```

---

## Task 6 — F-06 : Documenter la contrainte HKDF sans sel

**Finding :** HKDF avec `salt=None` est valide RFC 5869 mais rend la rotation de master key contraignante. La documentation manque.

**Files:**
- Modify: `apps/api/app/modules/secrets/store.py`

- [ ] **Step 1 : Lire la fonction HKDF dans `store.py`**

```bash
grep -n "HKDF\|salt\|derive\|master_key" apps/api/app/modules/secrets/store.py | head -20
```

- [ ] **Step 2 : Ajouter un commentaire explicite**

Dans `apps/api/app/modules/secrets/store.py`, trouve le bloc HKDF et ajoute le commentaire :

```python
self._aes_key: bytes = HKDF(
    algorithm=hashes.SHA256(),
    length=32,
    salt=None,  # RFC 5869 §2.2 : salt=None équivaut à sel de zéros de taille HashLen.
                # La dérivation est déterministe : même master_key → même clé AES.
                # CONTRAINTE : une rotation de DEVGATE_MASTER_KEY nécessite un re-chiffrement
                # complet de tous les secrets en base. Voir docs/architecture/adr-002-secret-store-interne.md.
    info=b"devgate-secret-store-v1",
).derive(master_key)
```

- [ ] **Step 3 : Mettre à jour `adr-002` si le fichier existe**

```bash
ls docs/architecture/adr-002-secret-store-interne.md 2>/dev/null && echo "existe" || echo "absent"
```

Si le fichier existe, ajoute une section sur la rotation :

```bash
# Vérifier si une section rotation existe déjà
grep -n "rotation\|rotate\|re-chiffrement" docs/architecture/adr-002-secret-store-interne.md
```

Si absent, ajoute à la fin :

```markdown
## Contrainte de rotation

La clé AES est dérivée de `DEVGATE_MASTER_KEY` via HKDF avec `salt=None` (dérivation déterministe).
Une rotation de `DEVGATE_MASTER_KEY` nécessite :
1. Déchiffrer tous les secrets avec l'ancienne clé
2. Re-chiffrer avec la nouvelle clé
3. Mettre à jour `DEVGATE_MASTER_KEY` en production

Aucun outillage de rotation n'est fourni en v1. Prévoir ce chantier avant toute rotation.
```

- [ ] **Step 4 : Vérifier que tous les tests passent**

```bash
cd apps/api && .venv/bin/python -m pytest -x -q
```

- [ ] **Step 5 : Commit**

```bash
git add apps/api/app/modules/secrets/store.py
# Ajouter le fichier ADR si modifié
git add docs/architecture/adr-002-secret-store-interne.md 2>/dev/null || true
git commit -m "docs(secrets): documenter la contrainte HKDF sans sel et la procédure de rotation (F-06)"
```

---

## Self-Review

### Spec coverage
- ✅ M-06 — Security headers Next.js
- ✅ M-05 — Admin layout redirect sur erreur non gérée
- ✅ H-04 — Dev deps exclus de l'image Docker prod
- ✅ M-08 — Dépendances critiques épinglées
- ✅ F-05 — Validation UUID sur les routes
- ✅ F-06 — Contrainte HKDF documentée

### Points hors scope
- F-03 (session ID = PK) — écarté volontairement (invasif, FAIBLE)
- Nonces CSP pour Next.js — post-v1
