# DevGate

Portail d'accès sécurisé aux environnements de développement d'agence.

Le navigateur utilisateur parle à DevGate. DevGate parle aux environnements via Cloudflare Tunnel + Access service token.

## Stack

- Backend : **FastAPI** (Python 3.12) + **PostgreSQL**
- Frontend : **Next.js 15** + React 19 + TypeScript
- Transport : **Cloudflare Tunnel** + **Access** (service auth)

## Structure

```
apps/
├── api/              # FastAPI (auth, portal, admin, gateway)
│   ├── app/modules/  # auth, portal, admin, resources, audit, gateway, transport, email
│   └── tests/        # unit + integration, 37 tests
└── web/              # Next.js portal + back-office
    └── src/
        ├── app/
        │   ├── (auth)/     # E01-E03, E09 login flow
        │   ├── (portal)/   # portail (Plan 2)
        │   └── (admin)/    # back-office (Plan 3)
        └── components/

docs/
├── architecture/     # doctrine, target, system-design
├── contributing/     # frontend + backend
├── ds/mockups/       # 12 HTML mockups référence visuelle
├── planning/         # build plan
├── product/          # PRD, spec, cadrage
└── superpowers/plans/  # plans d'implémentation TDD
```

## Développement local

### Prérequis
- Docker + Docker Compose
- Python 3.12 (ou via Docker)
- Node.js 20+ et npm

### Setup

```bash
# 1. Variables d'environnement (copier les .example)
cp .env.example .env
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.local.example apps/web/.env.local

# 2. Lancer la stack
docker compose up -d

# 3. Appliquer les migrations (première fois)
docker compose run --rm api alembic upgrade head

# 4. Seed dev (admin + client démo)
docker compose run --rm api python -m app.seeds

# 5. Ouvrir http://localhost:3000
```

### Comptes de démo (seed)

| Email | Rôle | Usage |
|-------|------|-------|
| `admin@agence.fr` | `agency_admin` sur Agence | Accès back-office |
| `marie@client-x.com` | `client_member` sur Client X | Portail utilisateur |

Les magic links sont capturés en mémoire par `FakeEmailProvider` (voir les logs API ou la table `login_challenges` pour retrouver le token en dev).

### Tests

```bash
# Backend (pytest, 37 tests)
cd apps/api && pytest tests/ -v

# Frontend (Vitest, 11 tests)
cd apps/web && npm run test
```

### Vérif rapide via curl

```bash
# Health
curl http://localhost:8000/healthz

# Start login
curl -X POST http://localhost:8000/auth/start \
  -H "Content-Type: application/json" \
  -d '{"email":"marie@client-x.com"}'
```

## État du projet

- ✅ **Plan 1 — Fondations + Auth** (ce repo) : 20 tâches TDD, 48 tests green
  - Magic link + OTP + session cookie
  - Rate limit 5/10min par IP+email
  - Audit events structurés
  - 12 écrans mockups référencés
- ⏸️ Plan 2 — Portail utilisateur (Phase 3)
- ⏸️ Plan 3 — Back-office agence (Phase 4)
- ⏸️ Plan 4 — Gateway proxy (Phase 5)
- ⏸️ Plan 5 — Intégration Cloudflare + hardening (Phase 6+7)

## Documentation

- Architecture cible : `docs/architecture/target-architecture.md`
- Doctrine : `docs/architecture/architecture-doctrine.md`
- Contribution frontend / backend : `docs/contributing/`
- Mockups DS : `docs/ds/mockups/`
- Plans TDD : `docs/superpowers/plans/`

## Licence

Voir `LICENSE`.
