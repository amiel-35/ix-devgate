# API Reference — DevGate

Base URL (Docker) : `http://localhost:8001`
Base URL (local sans Docker) : `http://localhost:8000`

La documentation interactive Swagger est disponible à `/docs` uniquement quand `DEBUG=true`.

## Authentification

Toutes les routes sauf `/auth/start`, `/auth/verify` et `/healthz` requièrent une session active.
La session est transportée via un cookie `devgate_session` (HttpOnly, SameSite=lax).
Les routes `/admin/*` exigent en plus le rôle `agency_admin`.

---

## Module auth

Préfixe : `/auth`

### POST /auth/start

Initie un challenge de connexion (magic link ou OTP par email).

**Auth requise** : non

**Body**
```json
{
  "email": "user@example.com",
  "method": "magic_link"
}
```

| Champ | Type | Valeurs | Défaut |
|-------|------|---------|--------|
| `email` | string (email) | — | requis |
| `method` | string | `magic_link`, `otp` | `magic_link` |

**Réponse 200**
```json
{
  "ok": true,
  "method": "magic_link"
}
```

**Exemple curl**
```bash
curl -X POST http://localhost:8001/auth/start \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@agence.fr", "method": "magic_link"}'
```

**Notes** : Rate-limité par IP + email. En mode `fake` email (développement), le token apparaît dans les logs du processus ou l'UI Mailpit (`http://localhost:8125`).

---

### POST /auth/verify

Vérifie le token reçu par email et ouvre une session.

**Auth requise** : non

**Body**
```json
{
  "token": "<token reçu par email>"
}
```

**Réponse 200** — pose le cookie `devgate_session`
```json
{
  "ok": true,
  "session_created": true,
  "redirect_to": "/portal"
}
```

**Exemple curl**
```bash
curl -X POST http://localhost:8001/auth/verify \
  -H "Content-Type: application/json" \
  -c cookies.txt \
  -d '{"token": "abc123..."}'
```

---

### POST /auth/logout

Invalide la session courante et supprime le cookie.

**Auth requise** : session valide

**Body** : aucun

**Réponse 200**
```json
{"ok": true}
```

**Exemple curl**
```bash
curl -X POST http://localhost:8001/auth/logout \
  -b cookies.txt -c cookies.txt
```

---

## Module portal

Préfixe : `/` (pas de préfixe supplémentaire)

### GET /me

Retourne le profil de l'utilisateur connecté.

**Auth requise** : session valide

**Réponse 200**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "display_name": "Marie Chevalier"
}
```

**Exemple curl**
```bash
curl http://localhost:8001/me -b cookies.txt
```

---

### GET /me/environments

Retourne la liste des environnements accessibles par l'utilisateur connecté (filtrés par ses grants d'accès).

**Auth requise** : session valide

**Réponse 200**
```json
[
  {
    "id": "uuid",
    "organization_name": "Client X",
    "project_name": "Refonte site",
    "environment_name": "Staging principal",
    "kind": "staging",
    "url": "https://client-x-staging.devgate.local",
    "gateway_url": "/gateway/<env_id>/",
    "requires_app_auth": true,
    "status": "online"
  }
]
```

Valeurs possibles pour `kind` : `dev`, `staging`, `preview`, `internal`
Valeurs possibles pour `status` : `online`, `offline`, `unknown`

**Exemple curl**
```bash
curl http://localhost:8001/me/environments -b cookies.txt
```

---

### GET /me/sessions

Retourne toutes les sessions actives de l'utilisateur connecté.

**Auth requise** : session valide

**Réponse 200**
```json
[
  {
    "id": "uuid",
    "expires_at": "2026-04-28T10:00:00+00:00",
    "last_seen_at": "2026-04-21T10:00:00+00:00",
    "ip": "127.0.0.1",
    "user_agent": "Mozilla/5.0...",
    "is_current": true
  }
]
```

**Exemple curl**
```bash
curl http://localhost:8001/me/sessions -b cookies.txt
```

---

### DELETE /me/sessions/{session_id}

Révoque une session spécifique de l'utilisateur. Ne peut pas révoquer la session courante.

**Auth requise** : session valide

**Paramètre path** : `session_id` (UUID de la session à révoquer)

**Réponse 204** : aucun corps

**Exemple curl**
```bash
curl -X DELETE http://localhost:8001/me/sessions/uuid-de-la-session \
  -b cookies.txt
```

---

## Module gateway

Préfixe : `/gateway`

Le gateway proxifie les requêtes vers l'upstream Cloudflare de façon transparente.
L'upstream réel (`upstream_hostname`) n'est jamais exposé au navigateur.

### ANY /gateway/{env_id}/{path}

Proxifie une requête HTTP (GET, POST, PUT, PATCH, DELETE) vers l'upstream de l'environnement.

**Auth requise** : session valide + grant actif sur l'organisation du projet

**Paramètres path**
| Paramètre | Description |
|-----------|-------------|
| `env_id` | UUID de l'environnement DevGate |
| `path` | Chemin relatif à transmettre à l'upstream |

**Headers injectés automatiquement**
| Header | Valeur |
|--------|--------|
| `X-DevGate-User` | UUID de l'utilisateur connecté |
| `CF-Access-Client-Id` | Client ID du service token (si configuré) |
| `CF-Access-Client-Secret` | Client Secret du service token (si configuré) |

**Headers supprimés avant transmission**
`host`, `cookie`, `accept-encoding`, `x-devgate-user` (anti-spoofing)

**Erreurs possibles**
| Code | Cause |
|------|-------|
| 401 | Session absente ou expirée |
| 403 | Grant absent ou révoqué |
| 404 | Environnement introuvable |
| 502 | Upstream injoignable (ConnectError) |
| 504 | Upstream timeout |

**Exemple curl**
```bash
# Accès à la racine de l'environnement
curl http://localhost:8001/gateway/<env_id>/ -b cookies.txt

# Accès à un sous-chemin
curl http://localhost:8001/gateway/<env_id>/api/data -b cookies.txt
```

---

### WebSocket /gateway/{env_id}/{path}

Proxy WebSocket bidirectionnel vers l'upstream.

**Auth** : cookie `devgate_session` présent dans la requête WebSocket (pas de header Authorization).

**Codes de fermeture**
| Code | Cause |
|------|-------|
| 1008 | Session absente, expirée ou grant invalide |
| 1011 | Upstream non configuré |

---

## Module admin

Préfixe : `/admin`
**Toutes les routes exigent le rôle `agency_admin`.**

### GET /admin/stats

Retourne les compteurs globaux.

**Réponse 200**
```json
{
  "active_orgs": 3,
  "active_envs": 8,
  "active_users": 12,
  "events_today": 47
}
```

**Exemple curl**
```bash
curl http://localhost:8001/admin/stats -b cookies.txt
```

---

### GET /admin/organizations

Liste toutes les organisations avec leurs compteurs d'environnements et d'utilisateurs.

**Query params** : aucun

**Réponse 200**
```json
[
  {
    "id": "uuid",
    "name": "Client X",
    "slug": "client-x",
    "branding_name": null,
    "support_email": null,
    "env_count": 2,
    "user_count": 3
  }
]
```

---

### POST /admin/organizations

Crée une organisation (client).

**Body**
```json
{
  "name": "Client X",
  "slug": "client-x",
  "branding_name": "Client X Corp",
  "support_email": "support@client-x.com"
}
```

**Réponse 201**
```json
{"id": "uuid"}
```

**Exemple curl**
```bash
curl -X POST http://localhost:8001/admin/organizations \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"name": "Client X", "slug": "client-x"}'
```

---

### GET /admin/projects

Liste les projets. Filtrable par organisation.

**Query params**
| Paramètre | Type | Description |
|-----------|------|-------------|
| `org_id` | string (optionnel) | Filtre par `organization_id` |

**Réponse 200**
```json
[
  {
    "id": "uuid",
    "organization_id": "uuid",
    "name": "Refonte site",
    "slug": "refonte-site"
  }
]
```

---

### POST /admin/projects

**Body**
```json
{
  "organization_id": "uuid",
  "name": "Refonte site",
  "slug": "refonte-site"
}
```

**Réponse 201**
```json
{"id": "uuid"}
```

---

### GET /admin/environments

Liste tous les environnements avec le dernier snapshot de santé.

**Réponse 200**
```json
[
  {
    "id": "uuid",
    "project_id": "uuid",
    "name": "Staging principal",
    "slug": "staging",
    "kind": "staging",
    "public_hostname": "client-x-staging.devgate.local",
    "requires_app_auth": true,
    "status": "active",
    "cloudflare_tunnel_id": "abc-tunnel-id",
    "org_name": "Client X",
    "project_name": "Refonte site",
    "health_status": "online",
    "health_latency_ms": 142
  }
]
```

---

### POST /admin/environments

**Body**
```json
{
  "project_id": "uuid",
  "name": "Staging principal",
  "slug": "staging",
  "kind": "staging",
  "public_hostname": "client-x-staging.devgate.local",
  "upstream_hostname": "abc.cfargotunnel.com",
  "requires_app_auth": false
}
```

Valeurs acceptées pour `kind` : `dev`, `staging`, `preview`, `internal`

**Réponse 201**
```json
{"id": "uuid"}
```

---

### POST /admin/environments/{env_id}/ping

Déclenche un health check immédiat sur l'upstream de l'environnement.

**Réponse 200**
```json
{
  "environment_id": "uuid",
  "status": "online",
  "observed_at": "2026-04-21T10:00:00+00:00",
  "latency_ms": 142
}
```

**Exemple curl**
```bash
curl -X POST http://localhost:8001/admin/environments/<env_id>/ping -b cookies.txt
```

---

### PUT /admin/environments/{env_id}/service-token

Stocke ou remplace le service token Cloudflare Access d'un environnement.
Le token est chiffré en base via le `SecretStore` — jamais stocké en clair.

**Body**
```json
{
  "client_id": "xxx.access.example.com",
  "client_secret": "yyy..."
}
```

**Réponse 200**
```json
{"ok": true}
```

**Exemple curl**
```bash
curl -X PUT http://localhost:8001/admin/environments/<env_id>/service-token \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"client_id": "xxx", "client_secret": "yyy"}'
```

---

### GET /admin/access-grants

Liste tous les grants d'accès (actifs et révoqués).

**Réponse 200**
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "user_email": "marie@client-x.com",
    "organization_id": "uuid",
    "org_name": "Client X",
    "role": "client_member",
    "created_at": "2026-04-21T10:00:00+00:00",
    "revoked_at": null
  }
]
```

---

### POST /admin/access-grants

Crée un grant d'accès. Crée l'utilisateur s'il n'existe pas encore.

**Body**
```json
{
  "email": "marie@client-x.com",
  "organization_id": "uuid",
  "role": "client_member",
  "display_name": "Marie Chevalier"
}
```

Valeurs acceptées pour `role` : `client_member`, `reviewer`, `agency_admin`

**Réponse 201**
```json
{"id": "uuid"}
```

---

### DELETE /admin/access-grants/{grant_id}

Révoque un grant d'accès (opération idempotente).

**Réponse 204** : aucun corps

---

### GET /admin/audit-events

Liste les événements d'audit par ordre décroissant.

**Query params**
| Paramètre | Type | Défaut | Maximum |
|-----------|------|--------|---------|
| `limit` | integer | 50 | 200 |
| `offset` | integer | 0 | — |

**Réponse 200**
```json
[
  {
    "id": "uuid",
    "actor_user_id": "uuid",
    "event_type": "gateway.resource.accessed",
    "target_type": "environment",
    "target_id": "uuid",
    "metadata_json": {"status_code": 200, "path": "/", "latency_ms": 142},
    "created_at": "2026-04-21T10:00:00+00:00"
  }
]
```

**Types d'événements courants**
| Type | Déclencheur |
|------|-------------|
| `admin.organization.created` | Création d'une organisation |
| `admin.project.created` | Création d'un projet |
| `admin.environment.created` | Création d'un environnement |
| `admin.environment.activated` | Provisioning CF terminé |
| `admin.access_grant.created` | Grant créé |
| `admin.access_grant.revoked` | Grant révoqué |
| `admin.service_token.stored` | Service token stocké |
| `admin.tunnel.assigned` | Tunnel CF assigné à un environnement |
| `gateway.resource.accessed` | Requête proxifiée avec succès |
| `gateway.request.failed` | Échec upstream (timeout ou connexion) |

---

### GET /admin/gateway-stats

Stats des requêtes gateway sur les 24 dernières heures, agrégées depuis l'audit.

**Réponse 200**
```json
{
  "since_hours": 24,
  "total_requests": 157,
  "errors_5xx": 2,
  "cf_refused": 1,
  "upstream_unavailable": 0,
  "avg_latency_ms": 98,
  "p95_latency_ms": 312
}
```

---

### POST /admin/sync-tunnels

Déclenche une synchronisation des tunnels Cloudflare (requiert `CF_API_TOKEN` et `CF_ACCOUNT_ID`).

**Réponse 200** : résumé de la synchronisation

**Réponse 503** si les credentials CF ne sont pas configurés.

---

### GET /admin/discovered-tunnels

Liste les tunnels découverts lors de la dernière sync Cloudflare.

**Réponse 200**
```json
[
  {
    "id": "uuid",
    "cloudflare_tunnel_id": "cf-tunnel-uuid",
    "name": "mon-tunnel-prod",
    "status": "discovered",
    "last_seen_at": "2026-04-21T10:00:00+00:00"
  }
]
```

Valeurs de `status` : `discovered`, `assigned`, `orphaned`

---

### POST /admin/discovered-tunnels/{tunnel_id}/assign

Affecte un tunnel découvert à un environnement DevGate. Met à jour `cloudflare_tunnel_id` et `upstream_hostname` sur l'environnement.

**Body**
```json
{
  "environment_id": "uuid"
}
```

**Réponse 200**
```json
{"ok": true}
```

---

### POST /admin/environments/{env_id}/activate

Lance le provisioning Cloudflare pour un environnement (saga ADR-001).
Requiert : credentials CF configurés + tunnel assigné sur l'environnement.

**Réponse 200**
```json
{
  "job_id": "uuid",
  "state": "active"
}
```

En cas d'échec partiel :
```json
{
  "job_id": "uuid",
  "state": "failed_recoverable",
  "error": "description de l'erreur"
}
```

---

## Endpoint de santé

### GET /healthz

**Auth requise** : non

**Réponse 200**
```json
{"ok": true}
```
