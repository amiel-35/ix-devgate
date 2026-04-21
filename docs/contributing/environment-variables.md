# Variables d'environnement — DevGate

Source de vérité : `apps/api/app/config.py` (pydantic-settings)

Les variables sont lues depuis le fichier `.env` dans `apps/api/` ou depuis l'environnement du processus.
Docker Compose peut injecter des surcharges directement via la section `environment:`.

---

## Référence complète

| Variable | Type | Défaut | Description | Requis en prod |
|----------|------|--------|-------------|----------------|
| `ENV` | string | `development` | Mode d'exécution. Valeurs : `development`, `production` | non |
| `DEBUG` | boolean | `false` | Active les logs détaillés et le Swagger UI sur `/docs` | non |
| `DATABASE_URL` | string | `postgresql+psycopg://devgate:devgate@localhost:5432/devgate` | URL de connexion PostgreSQL (format SQLAlchemy asyncpg) | oui |
| `SESSION_SECRET_KEY` | string | `changeme` | Clé de signature des cookies de session. Doit être longue et aléatoire en production | oui |
| `SESSION_TTL_DAYS` | integer | `7` | Durée de vie des sessions en jours | non |
| `COOKIE_SECURE` | boolean | `false` | Marque le cookie `devgate_session` comme `Secure` (HTTPS uniquement). Doit être `true` en production | oui |
| `EMAIL_PROVIDER` | string | `fake` | Fournisseur email. Valeurs : `fake`, `smtp`, `resend` | oui |
| `RESEND_API_KEY` | string | `""` | Clé API Resend (requis si `EMAIL_PROVIDER=resend`) | conditionnel |
| `SMTP_HOST` | string | `localhost` | Hôte SMTP | conditionnel |
| `SMTP_PORT` | integer | `1025` | Port SMTP | conditionnel |
| `SMTP_FROM` | string | `DevGate <no-reply@devgate.local>` | Adresse expéditeur des emails | conditionnel |
| `SMTP_USER` | string | `""` | Login SMTP (Brevo : email du compte) | conditionnel |
| `SMTP_PASSWORD` | string | `""` | Mot de passe SMTP (Brevo : clé API SMTP) | conditionnel |
| `FRONTEND_BASE_URL` | string | `http://localhost:3000` | URL de base du frontend — utilisée pour construire les magic links envoyés par email | oui |
| `CF_API_TOKEN` | string | `""` | Token API Cloudflare. Requis pour le provisioning CF et la sync des tunnels. Jamais exposé au frontend | conditionnel |
| `CF_ACCOUNT_ID` | string | `""` | ID du compte Cloudflare. Requis pour le provisioning CF | conditionnel |
| `CF_ZONE_ID` | string | `""` | ID de la zone DNS Cloudflare pour la publication des hostnames | conditionnel |
| `DEVGATE_MASTER_KEY` | string | `""` | Clé maître AES-256 encodée en base64 (32 bytes). Requise pour le chiffrement des service tokens CF. Doit être hors base et hors repo | oui (si CF) |

---

## Notes par variable

### `DATABASE_URL`

Le driver attendu est `psycopg` (psycopg3). En développement sans Docker, PostgreSQL doit être accessible localement. Les tests unitaires utilisent SQLite en mémoire — cette variable n'est pas lue pendant les tests.

### `SESSION_SECRET_KEY`

Génération recommandée en production :
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### `EMAIL_PROVIDER`

- `fake` : les tokens sont loggués dans la console du processus (dev uniquement)
- `smtp` : envoi via serveur SMTP — utiliser Mailpit en local, Brevo/Mailgun/SES en prod
- `resend` : envoi via l'API HTTP Resend

En développement Docker, Mailpit est fourni sur `localhost:1125` (SMTP) et `localhost:8125` (UI web).

### `FRONTEND_BASE_URL`

Utilisée uniquement côté backend pour construire les URLs des magic links.

- Docker : `http://localhost:3001`
- Local sans Docker : `http://localhost:3000`
- Production : `https://votre-domaine.com`

### `CF_API_TOKEN`, `CF_ACCOUNT_ID`, `CF_ZONE_ID`

Ces trois variables sont optionnelles en développement. Sans elles :
- `/admin/sync-tunnels` et `/admin/environments/{id}/activate` retournent 503
- Le reste de l'application fonctionne normalement

En production, le token doit avoir les permissions : `Cloudflare Tunnel:Edit`, `Access: Apps and Policies:Edit`, `DNS:Edit`.

### `DEVGATE_MASTER_KEY`

Clé AES-256 pour le chiffrement des secrets stockés en base (service tokens CF).

Génération :
```bash
python3 -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
```

Règles de gestion (ADR-002) :
- Ne jamais stocker dans la base de données
- Ne jamais committer dans le repo
- Injecter via variable d'environnement ou secret manager (AWS Secrets Manager, Vault, etc.)
- Si absente, le secret store lève une `RuntimeError` — les service tokens CF ne sont pas lisibles

---

## Exemple de fichier `.env` minimal pour le développement local

```dotenv
ENV=development
DEBUG=true
DATABASE_URL=postgresql+psycopg://devgate:devgate@localhost:5432/devgate
SESSION_SECRET_KEY=dev-local-insecure-changeme
COOKIE_SECURE=false
EMAIL_PROVIDER=smtp
SMTP_HOST=localhost
SMTP_PORT=1125
SMTP_FROM=DevGate <no-reply@devgate.local>
FRONTEND_BASE_URL=http://localhost:3001
DEVGATE_MASTER_KEY=
```

## Exemple de configuration production

```dotenv
ENV=production
DEBUG=false
DATABASE_URL=postgresql+psycopg://user:password@db-host:5432/devgate
SESSION_SECRET_KEY=<64-char-random-hex>
SESSION_TTL_DAYS=7
COOKIE_SECURE=true
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.brevo.com
SMTP_PORT=587
SMTP_FROM=DevGate <no-reply@votredomaine.com>
SMTP_USER=login@brevo-account.com
SMTP_PASSWORD=<brevo-smtp-api-key>
FRONTEND_BASE_URL=https://votredomaine.com
CF_API_TOKEN=<cloudflare-api-token>
CF_ACCOUNT_ID=<cloudflare-account-id>
CF_ZONE_ID=<cloudflare-zone-id>
DEVGATE_MASTER_KEY=<base64-encoded-32-bytes>
```
