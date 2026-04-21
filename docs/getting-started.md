# Getting Started — DevGate

Guide de démarrage pour les développeurs qui reprennent le projet ou contribuent pour la première fois.

## Prérequis

| Outil | Version minimale | Notes |
|-------|-----------------|-------|
| Python | 3.11 | Backend FastAPI |
| Node.js | 18 LTS | Frontend Next.js |
| Docker + Docker Compose | 24+ | Recommandé pour le dev local |
| PostgreSQL | 16 | Fourni par Docker Compose |

---

## Setup avec Docker Compose (recommandé)

Docker Compose démarre tous les services : base de données, mailpit, API et frontend.

### 1. Copier les fichiers d'environnement

```bash
cp apps/api/.env.example apps/api/.env       # si le fichier existe
cp apps/web/.env.local.example apps/web/.env.local  # si le fichier existe
```

Si les fichiers `.env.example` n'existent pas encore, crée `apps/api/.env` avec le contenu minimal :

```dotenv
ENV=development
DEBUG=true
SESSION_SECRET_KEY=devlocal-changeme
EMAIL_PROVIDER=smtp
SMTP_HOST=localhost
SMTP_PORT=1125
FRONTEND_BASE_URL=http://localhost:3001
DEVGATE_MASTER_KEY=
```

Pour activer le chiffrement des secrets (service tokens CF), génère une master key :

```bash
python3 -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
```

Copie le résultat dans `DEVGATE_MASTER_KEY`. Si la variable est absente, le secret store ne fonctionne pas (les tokens CF ne peuvent pas être stockés ni lus), mais le reste de l'application fonctionne.

### 2. Démarrer les services

```bash
docker compose up
```

### Ports exposés

| Service | URL | Description |
|---------|-----|-------------|
| API FastAPI | http://localhost:8001 | Backend (interne : 8000) |
| Frontend Next.js | http://localhost:3001 | Interface utilisateur |
| Mailpit UI | http://localhost:8125 | Boîte mail de dev (magic links et OTP) |
| Mailpit SMTP | localhost:1125 | SMTP local (pour l'API hors Docker) |
| PostgreSQL | localhost:5432 | Base de données |

### 3. Charger les données de test (seed)

Le seed crée les utilisateurs et données de démo. À exécuter une seule fois :

```bash
docker compose exec api python -m app.seeds
```

Le seed est idempotent : si des données existent déjà, il ne fait rien.

---

## Setup sans Docker

### Backend (apps/api)

#### 1. Créer le virtualenv

```bash
cd apps/api
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

#### 2. Configurer l'environnement

Créer `apps/api/.env` (voir section Docker pour le contenu minimal).
Pour PostgreSQL local, adapter `DATABASE_URL` :

```dotenv
DATABASE_URL=postgresql+psycopg://devgate:devgate@localhost:5432/devgate
```

#### 3. Appliquer les migrations Alembic

```bash
cd apps/api
.venv/bin/alembic upgrade head
```

#### 4. Charger le seed

```bash
cd apps/api
.venv/bin/python -m app.seeds
```

#### 5. Démarrer l'API

```bash
cd apps/api
.venv/bin/uvicorn app.main:app --reload --port 8000
```

L'API est disponible sur http://localhost:8000.

---

### Frontend (apps/web)

#### 1. Installer les dépendances

```bash
cd apps/web
npm install
```

#### 2. Configurer l'environnement

Créer `apps/web/.env.local` :

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
```

#### 3. Démarrer le serveur de développement

```bash
cd apps/web
npm run dev
```

Le frontend est disponible sur http://localhost:3000.

---

## Exécuter les tests

Les tests s'exécutent depuis le virtualenv du backend. Ne jamais utiliser le Python système.

```bash
cd apps/api
.venv/bin/python -m pytest
```

Pour les tests avec sortie verbeuse :

```bash
cd apps/api
.venv/bin/python -m pytest -v
```

Pour un seul fichier ou module :

```bash
cd apps/api
.venv/bin/python -m pytest tests/test_auth.py -v
```

Les tests utilisent SQLite en mémoire par défaut. Aucune base PostgreSQL n'est requise pour lancer les tests.

---

## Comptes de test (seed)

| Email | Rôle | Accès |
|-------|------|-------|
| `admin@agence.fr` | `agency_admin` | Back-office complet |
| `amiel@lavon.fr` | `agency_admin` | Back-office complet |
| `marie@client-x.com` | `client_member` | Portail — organisation "Client X" |

Ces comptes n'ont pas de mot de passe. Pour se connecter :

1. Envoyer une requête `POST /auth/start` avec l'email voulu et `"method": "magic_link"`
2. Ouvrir Mailpit sur http://localhost:8125 (Docker) ou http://localhost:8025 (local sans Docker)
3. Cliquer sur le lien de connexion reçu ou copier le token

Exemple rapide via curl :

```bash
curl -X POST http://localhost:8001/auth/start \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@agence.fr", "method": "magic_link"}'
```

---

## Structure des répertoires

```
.
├── apps/
│   ├── api/                   # Backend FastAPI
│   │   ├── app/
│   │   │   ├── modules/       # Modules métier (auth, portal, admin, gateway…)
│   │   │   ├── shared/        # Modèles, dépendances, exceptions partagées
│   │   │   ├── migrations/    # Migrations Alembic
│   │   │   ├── config.py      # Variables d'environnement (pydantic-settings)
│   │   │   ├── main.py        # Point d'entrée FastAPI
│   │   │   └── seeds.py       # Données de développement
│   │   └── tests/
│   └── web/                   # Frontend Next.js
├── docs/                      # Documentation projet
└── docker-compose.yml
```

---

## Ressources utiles

- [Référence API](api/README.md) — tous les endpoints documentés
- [Modèle de données](architecture/data-model.md) — schéma et relations
- [Variables d'environnement](contributing/environment-variables.md) — référence complète
- [Contribution backend](contributing/backend-contribution.md) — règles de code
- [ADR-001 — Cloudflare autodiscovery](architecture/adr-001-cloudflare-autodiscovery.md)
- [ADR-002 — Secret store interne](architecture/adr-002-secret-store-interne.md)
