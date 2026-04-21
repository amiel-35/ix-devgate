# DevGate

Portail d'accès sécurisé aux environnements de développement — sans exposer les serveurs.

**Version** : v1 — livré le 2026-04-21 | **Statut** : Production-ready

---

## Présentation

DevGate est un portail que les agences déploient pour donner à leurs clients un accès contrôlé à leurs environnements de dev, staging ou preview. L'utilisateur se connecte sur une interface brandée agence, voit les ressources auxquelles il a accès, et les ouvre directement depuis le portail — sans jamais connaître l'adresse réelle du serveur.

Le produit repose sur quatre blocs : authentification sans mot de passe (magic link / OTP), portail utilisateur par organisation, back-office agence pour gérer les clients et les ressources, et un gateway intégré qui proxifie les requêtes vers les upstreams via Cloudflare Tunnel. Le navigateur ne communique qu'avec DevGate. Les credentials Cloudflare restent côté serveur.

Ce que ça remplace ou évite : un VPN, un bastion SSH, un partage de credentials d'accès direct, ou une collection de bookmarks que l'agence maintient à la main. L'accès est audité, révocable, et visible en temps réel dans l'interface admin.

---

## Architecture

### Flux de bout en bout

```
Navigateur utilisateur
        |
        v
  [ DevGate portal ]  <- Next.js (portail + back-office)
        |
        v
  [ DevGate API ]     <- FastAPI (auth · session · gateway · audit · admin)
        |
   vérification session + grant
        |
        v
  [ Cloudflare Access ]  <- service token injecté par DevGate
        |
        v
  [ Cloudflare Tunnel ]  <- cloudflared sur le serveur cible
        |
        v
  [ Upstream ]           <- serveur dev / staging / preview
```

Le navigateur ne voit jamais le hostname Cloudflare brut ni l'URL réelle de l'upstream. DevGate est l'unique point d'entrée.

### Stack

| Composant | Technologie | Version |
|-----------|------------|---------|
| Frontend | Next.js + React + TypeScript | Next.js 15 / React 19 |
| Backend | FastAPI + Python | FastAPI 0.136 |
| Base de données | PostgreSQL | 16 |
| Transport | Cloudflare Tunnel + Cloudflare Access | — |
| Chiffrement secrets | AES-256-GCM (bibliothèque `cryptography`) | — |
| Tests backend | pytest + pytest-asyncio | — |
| Tests frontend | Vitest + Testing Library | — |

### Monolithe modulaire

DevGate est construit comme un monolithe modulaire à deux runtimes : une web app Next.js et une API FastAPI. Il n'y a pas de microservices. Cette décision est délibérée : la taille de l'équipe, les volumes cibles (~50-75 utilisateurs, ~20-25 environnements) et la complexité du produit ne justifient pas une architecture distribuée. Un monolithe est plus simple à déployer, déboguer et faire évoluer.

Le code est structuré par capacité métier, pas par type technique :

- `auth` — challenges, sessions, magic link, OTP
- `portal` — vues portail et page client
- `gateway` — vérification session/grant, proxy HTTP/WebSocket, gestion erreurs upstream
- `admin` — CRUD organisations, projets, environnements, utilisateurs
- `audit` — journal événementiel append-only
- `cloudflare` — autodiscovery tunnels, provisioning semi-assisté, health checks
- `secrets` — `SecretStore` avec chiffrement AES-256-GCM en base

### Secret store interne (ADR-002)

Les secrets serveur (service tokens Cloudflare Access, credentials email) sont chiffrés en base avec AES-256-GCM. Les objets métier ne stockent que des références (`secret_ref`). La master key (`DEVGATE_MASTER_KEY`) est hors base et hors repo — elle doit être injectée via variable d'environnement au démarrage.

Règle absolue : aucun secret ne doit apparaître dans le frontend, les logs, les réponses d'erreur ou les événements d'audit.

---

## Choix techniques clés

### 1. Gateway intégré au backend

Le gateway vit dans le même déploiement FastAPI, pas dans un service séparé. Il constitue une couche logique distincte avec ses propres règles (vérification session, résolution ressource, injection credentials, proxy, gestion erreurs). Ce n'est pas un ensemble de routes improvisées. Le séparer en service dédié serait une complexité inutile en v1.

### 2. Cloudflare Tunnel + Access comme transport

DevGate n'expose pas les serveurs directement sur Internet. Chaque upstream est protégé par un Cloudflare Tunnel et une application Cloudflare Access. DevGate injecte un service token côté serveur pour traverser cette barrière. Pas de VPN, pas de bastion, pas de règles firewall à maintenir. Le branchement Cloudflare en v1 est semi-assisté : la ressource est créée dans DevGate, puis rattachée à la configuration Cloudflare existante.

### 3. Secret store interne chiffré (pas de Vault externe en v1)

Un vault externe (HashiCorp Vault, Infisical, 1Password Connect) ajoute une dépendance opérationnelle dès le premier déploiement. Pour la cible v1 — une agence, des secrets principalement révocables chez Cloudflare — un store interne AES-256-GCM en base PostgreSQL est suffisant, plus simple à opérer, et réversible : migrer vers un vault externe reste possible sans changer le contrat d'interface `SecretStore`.

### 4. Magic link + OTP (pas de mot de passe)

Les utilisateurs finaux sont des clients d'agence, pas des administrateurs techniques. Un login par magic link (email) ou OTP à 6 chiffres élimine la gestion de mots de passe, les politiques de rotation, et les risques associés. Les challenges ont une durée de vie courte et sont à usage unique. Le rate limiting protège le démarrage de login.

### 5. Modèle d'accès par organisation (pas par ressource en v1)

Un utilisateur rattaché à une organisation voit toutes les ressources de cette organisation. Il n'y a pas de permissions fines par ressource en v1. Ce choix couvre 100% des cas d'usage identifiés et évite une complexité IAM prématurée. Les permissions par ressource sont une évolution post-v1 documentée.

---

## Features v1

Toutes les fonctionnalités suivantes sont implémentées et satisfont la Definition of Done v1.

**Authentification**
- Magic link par email (token à usage unique, TTL court)
- OTP 6 chiffres par email
- Sessions persistantes avec cookie sécurisé (TTL 7 jours)
- Rate limiting sur le démarrage de login
- Écrans d'état : lien expiré, session expirée, accès refusé

**Portail utilisateur**
- Interface brandée agence (nom, logo, couleur)
- Navigation par organisation
- Page client avec liste des environnements accessibles
- Fiche détail environnement (statut, accès direct)
- Écran interstitiel pour les ressources avec auth applicative propre
- Profil utilisateur et déconnexion

**Back-office agence**
- CRUD organisations, projets, environnements
- Gestion des utilisateurs et des accès (access grants par organisation)
- Vue audit : journal des événements consultable
- Vue connexions effectives en temps réel
- Statut de santé des environnements (online / offline / unknown)
- Ping manuel d'un upstream depuis l'interface admin

**Gateway**
- Proxy HTTP vers l'upstream via Cloudflare Tunnel
- Support WebSocket
- Vérification session + grant avant toute proxification
- Injection des service tokens Cloudflare Access côté serveur
- Gestion des erreurs upstream (502, timeout, accès refusé)
- Les credentials Cloudflare ne sont jamais transmis au navigateur

**Cloudflare**
- Autodiscovery des tunnels Cloudflare existants
- Rattachement semi-assisté d'un environnement à un tunnel découvert
- Provisioning Cloudflare Access semi-automatique (création app, policy, service token)
- Persistance immédiate du service token dans le secret store
- Suivi des jobs de provisioning avec états intermédiaires

**Observabilité et sécurité**
- Audit événementiel sur tous les flux critiques (login, création, connexion effective)
- Health checks upstreams avec snapshots horodatés
- Secret store interne AES-256-GCM
- Migrations versionnées (Alembic)

---

## Features post-v1

Ce qui ne fait pas partie de la v1, par choix délibéré et non par oubli.

- **Auto-refresh health status** : polling périodique des upstreams avec mise à jour temps réel dans l'interface admin
- **Statistiques gateway par environnement** : breakdown des temps de réponse, erreurs 5xx, refus Access par ressource
- **Alerting sur seuils** : webhooks ou intégrations PagerDuty/Slack sur ressource KO
- **Full provisioning Cloudflare automatique** : création du tunnel lui-même, sans intervention manuelle sur l'infrastructure Cloudflare
- **SSO corporate pour les admins agence** : Office 365 / Azure AD pour les connexions back-office
- **Permissions fines par ressource** : le modèle v1 est par organisation — les permissions par environnement ou par projet sont une évolution future
- **Branding multi-client** : v1 = branding agence unique pour tous les clients
- **Multi-instances / scale-out** : le monolithe devient un goulot d'étranglement seulement à des volumes que la v1 ne cible pas

---

## Démarrage rapide

Voir le guide complet : [docs/getting-started.md](docs/getting-started.md)

```bash
# Démarrer les services locaux (PostgreSQL, Mailpit, API, web)
docker compose up -d

# API accessible sur  http://localhost:8001
# Frontend sur        http://localhost:3001
# Mailpit (emails)    http://localhost:8125
```

Les migrations sont appliquées automatiquement au démarrage de l'API. Un seed de démonstration est disponible pour peupler la base avec des données de test :

```bash
docker compose run --rm api python -m app.seeds
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/getting-started.md](docs/getting-started.md) | Setup local, variables d'environnement, premier démarrage |
| [docs/architecture/architecture-doctrine.md](docs/architecture/architecture-doctrine.md) | Règles d'architecture à respecter pendant le build |
| [docs/architecture/system-design-lots-3-4.md](docs/architecture/system-design-lots-3-4.md) | Design technique du gateway, back-office et audit |
| [docs/architecture/adr-001-cloudflare-autodiscovery.md](docs/architecture/adr-001-cloudflare-autodiscovery.md) | ADR : provisioning Cloudflare semi-auto et autodiscovery |
| [docs/architecture/adr-002-secret-store-interne.md](docs/architecture/adr-002-secret-store-interne.md) | ADR : stockage chiffré des secrets en v1 |
| [docs/product/specification-lots-1-2.md](docs/product/specification-lots-1-2.md) | Spécification fonctionnelle portail et modèle d'accès |
| [docs/contributing/backend-contribution.md](docs/contributing/backend-contribution.md) | Règles de contribution backend (FastAPI, modules, tests) |
| [docs/contributing/frontend-contribution.md](docs/contributing/frontend-contribution.md) | Règles de contribution frontend (Next.js, surfaces, mockups) |
| [docs/runbook-exploitation.md](docs/runbook-exploitation.md) | Runbook incidents : procédures diagnostic et résolution |
| [docs/planning/build-plan.md](docs/planning/build-plan.md) | Plan de build, phases, Definition of Done v1 |

---

## Variables d'environnement principales

| Variable | Obligatoire | Description |
|----------|------------|-------------|
| `DATABASE_URL` | Oui | URL PostgreSQL (`postgresql+psycopg://...`) |
| `DEVGATE_MASTER_KEY` | Oui (prod) | Clé maître AES-256 pour le secret store — hors base, hors repo |
| `SESSION_SECRET_KEY` | Oui (prod) | Clé de signature des cookies de session |
| `CF_API_TOKEN` | Oui (Cloudflare) | Token API Cloudflare — jamais exposé au frontend |
| `CF_ACCOUNT_ID` | Oui (Cloudflare) | Identifiant compte Cloudflare |
| `EMAIL_PROVIDER` | Non | `fake` (dev) / `smtp` / `resend` |
| `FRONTEND_BASE_URL` | Non | URL de base pour la construction des magic links |

Le fichier `.env.example` dans `apps/api/` liste toutes les variables disponibles.

---

## Contribuer

Avant de commencer, lire dans cet ordre :

1. `CLAUDE.md` — vision produit, règles d'architecture, points de non-dérive
2. [docs/architecture/architecture-doctrine.md](docs/architecture/architecture-doctrine.md) — garde-fous d'implémentation
3. Le guide de contribution correspondant ([backend](docs/contributing/backend-contribution.md) ou [frontend](docs/contributing/frontend-contribution.md))
4. Le mockup de l'écran concerné dans `docs/ds/mockups/`

Chaque contribution doit être simple à lire, testable, conforme aux mockups, et sans fuite de détails Cloudflare vers le navigateur.

---

## Licence

Voir `LICENSE`.
