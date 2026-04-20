# Tunnel Autodiscovery & Provisioning Cloudflare

## Contexte

DevGate est hébergé sur l'infrastructure de l'agence. Les serveurs qui font tourner les apps clients sont également gérés par l'agence. L'agence contrôle donc les deux côtés : le compte Cloudflare et les serveurs applicatifs.

Aujourd'hui (v1), la mise en place d'un environnement est entièrement manuelle :
1. L'agence crée le tunnel `cloudflared` sur le serveur
2. Configure Cloudflare Access depuis le dashboard
3. Crée un service token à la main
4. Renseigne tout dans le back-office DevGate

Cette feature automatise les étapes 2 à 4 et remonte les tunnels existants dans le back-office sans saisie manuelle.

---

## Expression de besoin

**En tant qu'opérateur agence**, je veux :

- Voir apparaître automatiquement dans le back-office DevGate tout tunnel `cloudflared` actif sur mon compte Cloudflare, sans avoir à le saisir manuellement.
- Assigner un tunnel découvert à un client (organisation + projet) depuis le back-office.
- Déclencher depuis DevGate la configuration Cloudflare Access (app + service token + policy) en un clic, sans jamais passer par le dashboard CF.
- Avoir la garantie que le tunnel reste inaccessible publiquement tant qu'il n'est pas activé dans DevGate.

---

## Fonctionnement envisagé

### 1. Création du tunnel (côté ops, sur le serveur)

L'opérateur installe `cloudflared` sur le serveur applicatif et crée le tunnel :

```bash
cloudflared tunnel create devgate-acme-staging
cloudflared tunnel run devgate-acme-staging
```

Le tunnel est actif chez Cloudflare mais **inaccessible publiquement** — aucune route DNS, aucune Access app.

> **Règle de sécurité :** à terme, ajouter une policy "Block All" par défaut dès la création du tunnel pour se prémunir contre tout accès accidentel pendant la fenêtre de configuration.

---

### 2. Sync automatique DevGate ← Cloudflare (toutes les minutes)

Un service de fond dans FastAPI interroge l'API Cloudflare périodiquement :

```
GET /accounts/{account_id}/cfd_tunnel
```

Pour chaque tunnel retourné :
- Si `cloudflare_tunnel_id` inconnu en DB → crée un `Environment` avec `status = "discovered"`, non assigné
- Si connu → met à jour le `status` (`online` / `offline`) selon l'état CF

Le back-office affiche une section **"Tunnels non assignés"** listant les environnements découverts en attente de configuration.

---

### 3. Assignation dans le back-office

L'opérateur voit le tunnel apparaître (max ~1 minute après `cloudflared tunnel run`).

Il renseigne :
- Organisation client
- Projet
- Nom d'affichage de l'environnement
- `public_hostname` souhaité (ex: `acme-staging.devgate.example.com`)
- Type (`staging` / `production` / etc.)

Puis clique sur **"Activer l'accès"**.

---

### 4. Activation : DevGate configure Cloudflare Access

À la validation, DevGate appelle l'API CF dans l'ordre sécurisé suivant :

```
1. CF API → créer Access application sur le hostname
2. CF API → créer service token  "devgate-{env.slug}"
3. CF API → créer policy "allow service token"
4. CF API → ajouter route DNS  hostname → tunnel
5. Démarrer cloudflared (si pas déjà actif)
6. Stocker tunnel_id, app_id, token_id en DB
7. Stocker client_id + client_secret dans le secret store
8. Marquer l'environnement status = "active"
```

> **La route DNS est créée en dernier**, une fois Access configuré. Il n'y a jamais de fenêtre d'exposition publique.

L'environnement devient immédiatement accessible via le gateway DevGate (`/gateway/{env_id}/`).

---

### 5. Statut en temps réel dans le portail

Le sync toutes les minutes met à jour `Environment.status` depuis l'état réel du tunnel CF :

| Statut CF | Statut DevGate |
|---|---|
| `active` (≥1 connexion) | `online` |
| `inactive` (0 connexion) | `offline` |
| Inconnu / absent | `unknown` |

Les utilisateurs du portail voient le statut à jour sans polling côté frontend — ils lisent simplement `/me/environments` qui reflète la DB.

---

## Architecture des composants

```
apps/api/app/modules/cloudflare/
├── client.py          # Wrapper API CF (tunnels + Access)
├── sync.py            # Tâche de fond : sync statuts tunnels
├── provisioner.py     # Activation : crée Access app + token + DNS
└── schemas.py         # Types Pydantic CF
```

Nouveaux champs sur `Environment` :
- `cloudflare_tunnel_id` — déjà présent (v1)
- `cloudflare_access_app_id` — déjà présent (v1)
- `cloudflare_service_token_id` — à ajouter (pour pouvoir révoquer)
- `provisioning_status` — `discovered | provisioning | active | failed`

Nouvelles env vars sur le serveur DevGate :
```
CF_API_TOKEN=...        # API token Cloudflare (scope : Tunnel + Access)
CF_ACCOUNT_ID=...       # ID du compte CF de l'agence
CF_ZONE_ID=...          # Zone DNS pour les routes hostname
```

---

## Ce qui reste hors scope

- Installation automatique de `cloudflared` sur les serveurs (SSH/Ansible) — l'opérateur gère l'infra
- Rotation automatique des service tokens
- Multi-compte Cloudflare (une seule agence, un seul compte CF en v1)
- Suppression automatique des tunnels depuis DevGate (action manuelle intentionnelle)

---

## Prochaines étapes

1. Écrire le plan d'implémentation (`docs/superpowers/plans/`)
2. Implémenter `cloudflare/client.py` + `sync.py` (tâche de fond)
3. Implémenter `cloudflare/provisioner.py` + endpoint `POST /admin/environments/{id}/activate`
4. Ajouter la section "Tunnels non assignés" dans le back-office
5. Migration DB : `provisioning_status` sur `Environment`
