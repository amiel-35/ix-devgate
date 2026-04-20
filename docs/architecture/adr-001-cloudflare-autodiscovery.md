---
status: draft
type: adr
id: ADR-001
date: 2026-04-20
owners:
  - DevGate
---

# ADR-001 — Autodiscovery et provisioning Cloudflare pour DevGate

## Statut

Proposé

## Contexte

DevGate veut piloter l'exposition securisee des environnements de dev via :

- `Cloudflare Tunnel` pour le transport ;
- `Cloudflare Access` pour la protection edge ;
- un back-office DevGate comme source de verite produit.

Le besoin initial etait de rendre le provisioning plus fluide :

- voir les tunnels existants ;
- les rattacher a un environnement DevGate ;
- activer Access + service token + DNS sans passer par le dashboard Cloudflare.

Le risque identifie est que Cloudflare modele des objets techniques :

- tunnels
- applications Access
- policies
- service tokens

alors que DevGate modele des objets produit :

- clients
- ressources
- environnements
- acces

Le deuxieme risque majeur est la fiabilite du provisioning :

- les appels Cloudflare ne sont pas transactionnels ;
- le `client_secret` d'un service token n'est visible qu'une seule fois au moment de sa creation ;
- un crash process au mauvais moment peut laisser des objets Cloudflare orphelins ou non reutilisables proprement.

## Problème

Deux choix structurants doivent etre fixes :

1. quelle est la source de verite principale :
   - DevGate
   - ou Cloudflare
2. quel modele d'execution adopte le provisioner :
   - flux synchrone "best effort"
   - ou orchestration fiable avec reprise et compensation

## Décision

### 1. Source de vérité

**DevGate reste la source de verite produit.**

Cloudflare est traite comme :

- une couche de transport et de protection ;
- une source de verite technique secondaire ;
- une source de reponse pour la reconciliation et la detection de derive.

Consequence :

- on ne cree pas automatiquement un `Environment` DevGate juste parce qu'un tunnel existe chez Cloudflare ;
- l'activation d'un environnement reste explicite dans DevGate ;
- l'autodiscovery sert surtout a :
  - remonter des candidats techniques ;
  - verifier l'etat reel ;
  - detecter les ressources orphelines ou incoherentes.

### 2. Mode de découverte retenu

**Autodiscovery retenue uniquement comme inventaire technique, pas comme creation automatique d'objet metier.**

Donc :

- un tunnel detecte peut apparaitre dans une liste de candidats ;
- l'operateur decide ensuite de l'assigner a un environnement DevGate ;
- cette assignation est une action produit explicite.

### 3. Mode de provisioning retenu

**Le provisioning Cloudflare est traite comme une saga avec reprise et compensation, pas comme une transaction.**

Consequence :

- on ne parle pas de rollback transactionnel ;
- on persiste l'etat de progression apres chaque etape distante ;
- on distingue les etats recuperables des etats terminalement echoues ;
- on prevoit des actions de compensation explicites.

## Pourquoi cette décision

### Pourquoi DevGate doit rester la source de vérité

Le modele DevGate est centre sur :

- clients
- ressources
- acces
- audit

Or un tunnel Cloudflare ne represente pas toujours un environnement metier.

Un tunnel peut correspondre a :

- un serveur ;
- un groupe d'apps ;
- plusieurs hostnames ;
- un point de transport technique sans valeur produit directe.

Si l'on laisse Cloudflare dicter la creation des environnements, on introduit :

- du bruit ;
- un couplage fort a la structure infra ;
- des surprises quand la topologie des tunnels change.

### Pourquoi un flux synchrone simple est insuffisant

Le provisioning implique plusieurs effets de bord distants :

1. creation application Access
2. creation policy
3. creation service token
4. creation DNS

Le point critique est l'etape `service token` :

- le secret n'est lisible qu'une seule fois ;
- s'il est perdu avant persistence durable, le token cree devient inutilisable par DevGate ;
- le systeme doit alors compenser ou recreer proprement.

Un simple enchainement synchrone HTTP est donc insuffisant pour garantir :

- l'idempotence ;
- la reprise apres crash ;
- la non-publication accidentelle ;
- la traçabilite fine.

## Modèle retenu

### Autodiscovery

Le job de sync Cloudflare :

- liste les tunnels ;
- met a jour leur disponibilite ;
- remonte les tunnels inconnus comme **candidats techniques** ;
- signale les derives entre Cloudflare et DevGate.

Il ne doit pas :

- creer automatiquement un environnement metier actif ;
- supposer `1 tunnel = 1 environnement`.

### Provisioning

Le provisioning est pilote par un objet durable en base, par exemple :

- `provisioning_job`

avec :

- `environment_id`
- `provider = cloudflare`
- `state`
- `attempt_count`
- `last_error`
- `cloudflare_access_app_id`
- `cloudflare_policy_id`
- `cloudflare_service_token_id`
- `secret_persisted`
- `dns_published`

### Etats minimaux recommandés

- `pending`
- `creating_access_app`
- `access_app_created`
- `creating_policy`
- `policy_created`
- `creating_service_token`
- `service_token_created_unsealed`
- `secret_persisted`
- `creating_dns`
- `active`
- `failed_recoverable`
- `failed_terminal`
- `compensating`
- `rolled_back`

## Règles d'orchestration

### R1 — Persist after each remote side effect

Apres chaque appel Cloudflare reussi, DevGate persiste :

- l'etat atteint ;
- les IDs Cloudflare utiles ;
- les metadonnees minimales de reprise.

### R2 — DNS last

Le DNS n'est cree qu'en dernier.

Condition obligatoire avant publication DNS :

- `secret_persisted = true`

### R3 — Token secret is a critical checkpoint

La creation du service token est une etape critique "create-and-seal".

Le workflow ne peut continuer vers le DNS que si :

- le token a ete cree ;
- son secret a ete persiste avec succes dans le secret store ;
- cette persistence a ete confirmee en base.

### R4 — No blind retry after token creation

Si un crash survient apres creation du token mais avant confirmation de persistence du secret :

- le job passe en `failed_recoverable` ;
- le systeme ne continue pas directement ;
- il doit d'abord :
  - soit revoquer puis recreer le token ;
  - soit effectuer une rotation/recreation explicite.

### R5 — Compensation is explicit

En cas d'echec, le moteur tente de compenser dans l'ordre inverse si possible :

1. supprimer DNS si cree
2. supprimer ou revoquer le service token
3. supprimer policy si dediee
4. supprimer application Access si dediee

Si la compensation complete echoue :

- l'objet reste en `failed_recoverable`
- avec la liste des ressources Cloudflare encore presentes.

## Séquence retenue

### Séquence nominale

1. creer ou charger l'environnement DevGate
2. creer `provisioning_job`
3. creer Access app
4. persister `access_app_id`
5. creer policy
6. persister `policy_id`
7. creer service token
8. persister temporairement les metadonnees de token
9. persister le secret dans le secret store
10. marquer `secret_persisted = true`
11. creer DNS
12. marquer l'environnement `active`

### Séquence d'échec critique

Cas :

- service token cree
- process mort avant persistence du secret

Conduite retenue :

1. reprise du job au redemarrage
2. detection que `service_token_id` existe mais `secret_persisted = false`
3. passage en `failed_recoverable`
4. compensation :
   - revoke/delete token
   - recreation du token
   - persistence du nouveau secret
5. seulement ensuite reprise vers DNS

## Conséquences

### Positives

- modele produit propre ;
- moins de couplage a la topologie Cloudflare ;
- meilleure auditabilite ;
- provisioning reprenable ;
- pas de fenetre d'exposition publique avant scellement du secret.

### Négatives

- plus de code d'orchestration ;
- besoin d'un secret store fiable ;
- besoin d'une table de jobs ou d'un state machine persiste ;
- UX back-office un peu moins "magique".

## Alternatives écartées

### A. Autodiscovery pure

Ecartee car :

- trop de couplage entre tunnel et environnement ;
- bruit si le compte Cloudflare contient d'autres tunnels ;
- glissement de la source de verite vers l'infra.

### B. Provisioning synchrone best effort

Ecarte car :

- trop fragile en cas de crash ;
- sous-specifie sur la reprise ;
- dangereux pour les secrets one-shot.

### C. GitOps / Terraform comme source de vérité principale

Ecarte pour la v1 car :

- robuste, mais trop lourd ;
- deplace trop tot la complexite vers l'infra.

## Implications pour l'implémentation

Le design cible doit inclure :

- un module `cloudflare sync`
- un module `cloudflare provisioner`
- une persistence d'etat de provisioning
- un secret store
- des jobs de retry et de compensation
- un audit des transitions d'etat

Le back-office doit distinguer :

- `candidat decouvert`
- `environnement assigne`
- `provisioning en cours`
- `actif`
- `echec recuperable`

## Ce qui reste ouvert

- choix exact du secret store v1 ;
- politique exacte de retry ;
- seuil entre `failed_recoverable` et `failed_terminal` ;
- granularite exacte des objets de decouverte si un tunnel expose plusieurs ingress.

## Conclusion

DevGate retient :

- **autodiscovery comme inventaire technique**
- **activation explicite cote DevGate**
- **provisioning Cloudflare comme saga fiable**

Le point critique du design est acte :

- **la creation du service token n'est pas une etape retry-safe tant que le secret n'est pas scelle**

Donc la seule conception acceptable est :

- persistence d'etat,
- DNS en dernier,
- compensation explicite,
- reprise controlee.
