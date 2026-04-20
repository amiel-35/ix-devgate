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
- Assigner un tunnel découvert à un client (organisation + projet) depuis le back-office, de manière explicite.
- Déclencher depuis DevGate la configuration Cloudflare Access (app + service token + policy + DNS) en un clic, sans jamais passer par le dashboard CF.
- Avoir la garantie que le tunnel reste inaccessible publiquement tant qu'il n'est pas activé dans DevGate.

---

## Modèle de données : tunnel ≠ environnement

> **Point d'architecture critique.**

Un tunnel Cloudflare est un **connecteur réseau**, pas un objet métier.  
Un même tunnel peut porter plusieurs `ingress` (hostname → service). Si l'infra évolue vers un tunnel par serveur ou un tunnel multi-apps, un mapping automatique "1 tunnel = 1 environnement" casse immédiatement.

Le bon découpage :

```
DiscoveredTunnel        — objet technique, miroir de l'état CF
    ↓ (assignation explicite par l'opérateur)
Environment             — objet produit DevGate (org + projet + hostname)
```

La découverte CF alimente un **inventaire de candidats transport**, pas des environnements.  
L'opérateur fait le lien explicitement. DevGate provisionne Access à ce moment-là.

---

## Fonctionnement envisagé

### 1. Création du tunnel (côté ops, sur le serveur)

L'opérateur installe `cloudflared` sur le serveur applicatif et crée le tunnel :

```bash
cloudflared tunnel create devgate-acme-staging
cloudflared tunnel run devgate-acme-staging
```

Le tunnel est actif chez Cloudflare mais **inaccessible** : aucune route DNS, aucune Access app.

> **Note sécurité :** Un tunnel sans route DNS n'est pas exploitable publiquement. La vraie protection se joue au niveau de l'**Access app** et du **DNS**, pas du tunnel lui-même. Le réglage org CF `deny_unmatched_requests` peut renforcer ça en bloquant tout hostname non couvert par une Access app.

---

### 2. Sync automatique DevGate ← Cloudflare (toutes les N minutes)

Un service de fond dans FastAPI interroge l'API Cloudflare :

```
GET /accounts/{account_id}/cfd_tunnel
```

Pour chaque tunnel retourné :
- Si `tunnel_id` inconnu en DB → crée un `DiscoveredTunnel` avec `status = "discovered"`
- Si connu → met à jour le statut de connexion

**Limite connue :** Cloudflare peut conserver une connexion comme `is_pending_reconnect` quelques minutes après déconnexion. Le statut `online/offline` dans DevGate est une bonne approximation, pas une vérité milliseconde.

**Convention de nommage recommandée** pour filtrer le bruit :  
Préfixer les tunnels destinés à DevGate : `devgate-*`. Le sync ignore les tunnels sans ce préfixe.

---

### 3. Inventaire dans le back-office

Une section **"Tunnels disponibles"** liste les `DiscoveredTunnel` non encore assignés.

Informations affichées par tunnel :
- Nom CF, statut connexion, date de création
- Nombre de connexions actives
- Hostname(s) ingress déjà configurés côté CF (lecture seule)

Ce n'est pas encore un environnement DevGate.

---

### 4. Assignation explicite par l'opérateur

L'opérateur sélectionne un tunnel et renseigne :
- Organisation client
- Projet
- Nom d'affichage
- `public_hostname` souhaité (ex: `acme-staging.devgate.example.com`)
- Type (`staging` / `production` / etc.)

Puis clique sur **"Activer l'accès"** → crée l'`Environment` et déclenche le provisioning.

---

### 5. Activation : DevGate provisionne Cloudflare Access

Ordre d'opérations sécurisé — **le DNS est ajouté en dernier** :

```
1. CF API → créer Access application sur le hostname
2. CF API → créer policy "allow service token devgate-{slug}"
3. CF API → créer service token "devgate-{slug}"
          → stocker immédiatement client_id + client_secret
            (le secret n'est visible qu'une seule fois, non récupérable)
4. CF API → ajouter route DNS  hostname → tunnel
5. DB     → lier DiscoveredTunnel à l'Environment
6. DB     → marquer provisioning_status = "active"
```

> **Contrainte critique : le `client_secret` du service token n'est visible qu'à la création.**  
> Cloudflare ne le ré-expose jamais. Si perdu → recréer ou rotation obligatoire.  
> Le flow de provisioning doit être transactionnel et capable de rollback.  
> Source : [Service tokens docs](https://developers.cloudflare.com/cloudflare-one/access-controls/service-credentials/service-tokens/)

---

### 6. Sync de statut et détection de dérive

Le sync périodique ne sert plus qu'à :
- Mettre à jour `Environment.status` (`online` / `offline` / `unknown`)
- Détecter les **tunnels orphelins** (tunnel CF actif mais plus d'Environment DevGate associé)
- Détecter les **dérives** (Access app supprimée manuellement depuis le dashboard CF)
- Remonter les nouveaux tunnels `devgate-*` dans l'inventaire

---

## Architecture des composants

```
apps/api/app/modules/cloudflare/
├── client.py          # Wrapper API CF (tunnels + Access + DNS)
├── sync.py            # Tâche de fond : sync inventaire + statuts
├── provisioner.py     # Activation : Access app + token + DNS
└── schemas.py         # Types Pydantic CF
```

### Nouveaux modèles DB

**`DiscoveredTunnel`** (nouvel objet) :
- `id` — UUID DevGate
- `cloudflare_tunnel_id` — ID CF
- `name` — nom CF
- `status` — `discovered | assigned | orphaned`
- `last_seen_at` — dernière fois vu dans le sync
- `metadata_json` — données brutes CF (connexions, version, etc.)

**Champs supplémentaires sur `Environment`** :
- `cloudflare_service_token_id` — pour pouvoir révoquer/rotater
- `provisioning_status` — `pending | provisioning | active | failed`
- `discovered_tunnel_id` — FK vers `DiscoveredTunnel`

### Nouvelles env vars

```
CF_API_TOKEN=...        # API token Cloudflare (scope : Tunnel + Access + DNS)
CF_ACCOUNT_ID=...       # ID du compte CF de l'agence
CF_ZONE_ID=...          # Zone DNS pour les routes hostname
```

---

## Ce qui reste hors scope

- Installation automatique de `cloudflared` sur les serveurs — l'opérateur gère l'infra
- Rotation automatique des service tokens (prévu en phase suivante)
- Multi-compte Cloudflare (une seule agence, un seul compte CF en v1)
- Suppression automatique des tunnels CF depuis DevGate (action manuelle intentionnelle)
- Provisioning via Terraform / GitOps (option C — plus robuste à terme, pas en v1)

---

## Références API Cloudflare

- [Tunnel API](https://developers.cloudflare.com/api/resources/zero_trust/subresources/tunnels/)
- [Access applications API](https://developers.cloudflare.com/api/resources/zero_trust/)
- [Service tokens API](https://developers.cloudflare.com/api/resources/zero_trust/subresources/access/subresources/service_tokens/)
- [DNS records API](https://developers.cloudflare.com/api/resources/dns/subresources/records/)
- [Tunnel routing](https://developers.cloudflare.com/tunnel/routing/)

---

## Prochaines étapes

1. Écrire le plan d'implémentation (`docs/superpowers/plans/`)
2. Migration DB : modèle `DiscoveredTunnel` + champs `Environment`
3. Implémenter `cloudflare/client.py` + `sync.py` (tâche de fond + inventaire)
4. Implémenter `cloudflare/provisioner.py` + endpoint `POST /admin/environments/{id}/activate`
5. Ajouter la section "Tunnels disponibles" dans le back-office
6. Gestion du rollback provisioning (service token secret perdu = recréation)
