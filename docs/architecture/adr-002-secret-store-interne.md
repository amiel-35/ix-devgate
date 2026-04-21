---
status: accepted
type: adr
id: ADR-002
date: 2026-04-21
owners:
  - DevGate
---

# ADR-002 - Secret store interne chiffre pour DevGate v1

## Statut

Accepte

## Contexte

DevGate doit manipuler des secrets serveur :

- service tokens `Cloudflare Access` ;
- token API Cloudflare ;
- credentials de provider email ;
- eventuels secrets de provisioning.

Le point le plus sensible est le `client_secret` des service tokens Cloudflare Access :

- il est visible une seule fois a la creation ;
- il doit etre persiste immediatement avant publication DNS ;
- s'il est perdu, DevGate doit revoquer ou recreer le token.

Une option externe type Infisical, Vault ou 1Password Connect reste possible, mais elle ajoute une dependance operationnelle des la v1.

La cible v1 est volontairement sobre :

- environ 50 a 75 utilisateurs ;
- environ 20 a 25 environnements ;
- une seule agence ;
- secrets principalement revocables chez Cloudflare.

## Probleme

Il faut choisir comment stocker les secrets sans :

- stocker de secret en clair dans PostgreSQL ;
- introduire un vault trop lourd pour la v1 ;
- bloquer le provisioning Cloudflare fiable de l'ADR-001 ;
- coupler tout le code a une solution impossible a migrer.

## Decision

DevGate v1 utilise un **secret store interne chiffre en base**, protege par une `master key` fournie hors base.

La decision est :

- `PostgreSQL` stocke uniquement des secrets chiffres et leurs metadonnees ;
- la `master key` n'est jamais stockee en base ;
- la `master key` est fournie par l'environnement de deploiement (`DEVGATE_MASTER_KEY`, secret Coolify, Docker secret ou equivalent) ;
- le chiffrement utilise une primitive standard authentifiee (`AES-256-GCM`), jamais une crypto maison ;
- l'application passe toujours par une interface `SecretStore` ;
- la base stocke une reference de secret, pas un secret en clair ;
- une migration future vers Infisical, Vault ou 1Password doit pouvoir se faire en remplacant l'implementation de `SecretStore`.

## Specification technique v1

### 1. Master key

`DEVGATE_MASTER_KEY` = 32 bytes aleatoires encodes en base64, generes une fois :

```bash
python3 -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

Regles :

- jamais dans Git ;
- jamais en base ;
- jamais prefixee `NEXT_PUBLIC_` ;
- jamais dans les logs ;
- jamais exposee au frontend.

### 2. Derivation de cle (KDF)

La master key n'est pas utilisee directement comme cle AES.

On derive une unique cle de chiffrement avec `HKDF-SHA256` :

```python
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

derived_key = HKDF(
    algorithm=hashes.SHA256(),
    length=32,
    salt=None,
    info=b"devgate-secret-store-v1",
).derive(master_key_bytes)
```

Le parametre `info = b"devgate-secret-store-v1"` est fixe et versionne.
Si le schema change, on bumpe en `v2` — ce qui invalide mecaniquement les anciens secrets.

Pas de sous-cles par type de secret en v1. Une seule cle derivee pour le store.

### 3. Chiffrement — AES-256-GCM

Un nonce aleatoire de 12 bytes par secret. AAD lie au contexte metier :

```python
import json
aad = json.dumps({
    "secret_ref": secret_ref,
    "secret_type": secret_type,
    "owner_type": owner_type,
    "owner_id": owner_id,
    "key_id": key_id,
}, sort_keys=True).encode()
```

L'AAD empeche qu'un ciphertext soit deplace silencieusement d'un contexte a un autre.
Le couple `(key, nonce)` ne doit jamais etre reutilise.

### 4. Format `secret_ref`

Opaque et stable : `sec_<ulid>` ou `sec_<uuidv7>`.

- pas de logique metier dans la ref ;
- le type est en colonne `secret_type`, pas dans la ref ;
- la ref est generee avant l'appel a l'encrypteur et sert d'AAD.

Ordre de bootstrap :

1. generer `secret_ref` (ULID) ;
2. construire l'AAD avec cette ref ;
3. chiffrer le secret avec l'AAD ;
4. persister le tout en base.

### 5. Rotation de cle

V1 minimaliste :

- `key_id = v1` au demarrage ;
- les nouveaux secrets utilisent la cle active ;
- les anciens secrets restent lisibles tant que l'ancienne cle est configuree ;
- pas de re-encryption automatique en v1.

En cas de fuite de la master key :

- on ne re-encrypte pas seulement ;
- on **revoque et renouvelle les secrets Cloudflare** (service tokens revocables) ;
- on regernere une nouvelle master key ;
- on re-provisionne les environnements concernes.

### 6. Stores de test

Deux implementations :

- `FakeSecretStore` — store en memoire, sans chiffrement, pour les tests unitaires ;
- `EncryptedDatabaseSecretStore` avec une master key fixe deterministe pour les tests d'integration.

```python
# Tests unitaires
store = FakeSecretStore()

# Tests d'integration
TEST_MASTER_KEY = base64.b64encode(b"a" * 32).decode()
store = EncryptedDatabaseSecretStore(master_key=TEST_MASTER_KEY, db=db_session)
```

## Pourquoi cette decision

### Pourquoi pas un vault externe obligatoire en v1

Un vault dedie apporte de vraies garanties :

- controle d'acces plus fin ;
- audit dedie ;
- rotation plus outillee ;
- separation operationnelle.

Mais pour DevGate v1, cela ajoute aussi :

- un composant critique supplementaire ;
- de la configuration ;
- des droits a gerer ;
- une panne possible de plus ;
- un cout cognitif et operationnel disproportionne.

La v1 a surtout besoin d'eviter le pire cas simple : **un dump PostgreSQL ne doit pas exposer les secrets Cloudflare en clair**.

### Pourquoi une master key hors base suffit pour v1

Le modele protege contre :

- fuite d'un backup PostgreSQL ;
- lecture accidentelle de tables ;
- export admin mal controle ;
- logs SQL ou dumps partiels.

Il ne protege pas contre :

- compromission complete du serveur applicatif ;
- fuite de la `master key` ;
- code applicatif malveillant ;
- mauvaise hygiene de logs.

Ce compromis est accepte parce que :

- les secrets principaux sont revocables ;
- les volumes sont limites ;
- DevGate reste mono-agence en v1 ;
- le cout et la simplicite sont des contraintes fortes.

## Modele retenu

### Interface obligatoire

Tout acces aux secrets doit passer par une abstraction serveur, par exemple :

```text
SecretStore
  put(secret_type, plaintext, metadata) -> secret_ref
  get(secret_ref) -> plaintext
  rotate(secret_ref, new_plaintext) -> new_secret_ref
  revoke(secret_ref) -> void
```

Le code metier ne doit pas connaitre :

- la table physique de stockage ;
- l'algorithme de chiffrement ;
- la forme exacte du ciphertext ;
- la source de la master key.

### Donnees stockees

Une table de secrets chiffres peut stocker :

- `id`
- `secret_ref`
- `secret_type`
- `owner_type`
- `owner_id`
- `key_id`
- `ciphertext`
- `nonce`
- `auth_tag`
- `algorithm`
- `metadata_json`
- `created_at`
- `rotated_at`
- `revoked_at`

Les tables metier stockent uniquement une reference, par exemple :

- `service_token_ref`
- `cloudflare_api_token_ref`
- `email_provider_secret_ref`

### Master key

Regles obligatoires :

- ne jamais commiter la `master key` ;
- ne jamais la stocker en base ;
- ne jamais la prefixer `NEXT_PUBLIC_` ;
- ne jamais l'exposer au frontend ;
- ne jamais l'afficher dans les logs ;
- prevoir `key_id` pour permettre une rotation future.

### Chiffrement

Regles obligatoires :

- utiliser `cryptography` (librairie Python maintenue) ;
- utiliser `AES-256-GCM` (chiffrement authentifie) ;
- generer un nonce aleatoire de 12 bytes par secret ;
- ne jamais reutiliser un couple `key + nonce` ;
- lier le ciphertext a son contexte metier via AAD ;
- ne jamais inventer un format cryptographique non documente.

## Integration avec ADR-001

Le provisioner Cloudflare doit respecter l'ordre suivant :

1. creer le service token Cloudflare ;
2. recevoir le secret one-shot ;
3. appeler `SecretStore.put(...)` ;
4. persister la reference retournee ;
5. marquer `secret_persisted = true` ;
6. publier le DNS uniquement ensuite.

Si l'etape 3 ou 4 echoue :

- le job passe en `failed_recoverable` ;
- DevGate ne publie pas le DNS ;
- le token Cloudflare doit etre revoque ou recree ;
- aucun retry aveugle ne doit supposer que le secret perdu est recuperable.

## Doctrine pour les agents

### A faire

- Utiliser `SecretStore` pour tout secret serveur.
- Stocker uniquement des references de secrets dans les objets metier.
- Traiter la `master key` comme une configuration de runtime.
- Utiliser `FakeSecretStore` pour les tests unitaires, `EncryptedDatabaseSecretStore` avec cle fixe pour les tests d'integration.
- Masquer les secrets dans les logs, erreurs, audit et payloads admin.
- Documenter toute nouvelle famille de secret dans ce fichier ou dans une ADR suivante.

### A ne pas faire

- Ne pas stocker un secret en clair en base.
- Ne pas stocker un secret dans un fichier versionne.
- Ne pas passer un secret au frontend.
- Ne pas logger les headers `CF-Access-Client-Secret`.
- Ne pas coupler le provisioner directement a PostgreSQL pour lire le ciphertext.
- Ne pas introduire Vault, Infisical ou 1Password comme dependance obligatoire sans nouvel ADR.
- Ne pas faire de "crypto maison".

## Consequences

### Positives

- v1 plus simple a deployer ;
- pas de composant vault a maintenir ;
- protection raisonnable contre les dumps de base ;
- cout fixe limite ;
- migration future possible via abstraction.

### Negatives

- la securite depend fortement de la protection de la `master key` ;
- l'application peut dechiffrer les secrets en runtime ;
- pas d'audit dedie de vault ;
- rotation initiale plus artisanale.

### Risques acceptes

- Une compromission complete du serveur applicatif expose potentiellement les secrets.
- Une perte de la `master key` rend les secrets indechiffrables.
- Une fuite de la `master key` impose rotation/revocation des secrets.

Ces risques sont acceptables en v1 uniquement parce que les secrets critiques sont revocables et que le produit reste mono-agence.

## Reversibilite

La decision reste reversible si :

- DevGate devient multi-agence ;
- plusieurs operateurs doivent avoir des droits differencies sur les secrets ;
- la rotation automatique devient obligatoire ;
- l'audit secret devient une exigence client ;
- les secrets manipules deviennent non revocables ou plus sensibles.

Dans ce cas, l'implementation `SecretStore` pourra etre remplacee par :

- Infisical ;
- 1Password Connect ;
- HashiCorp Vault ;
- ou un secret manager cloud.

## Decision courte

Pour DevGate v1 :

- **secret store interne chiffre en base**
- **master key hors base**
- **interface `SecretStore` obligatoire**
- **aucun secret en clair dans PostgreSQL**
- **aucun secret cote frontend**
- **migration vault possible plus tard, pas maintenant**
