# Doctrine d'architecture - DevGate

## Statut

Reference projet v1

## Objet

Fixer les regles d'architecture qui doivent rester stables pendant la construction de DevGate.

Ce document ne remplace pas :

- le `PRD`
- la `product spec`
- le `system design`

Il pose la doctrine qui doit guider les choix de build, de revue et de refactor.

## Sources de verite

Ordre de priorite recommande :

1. besoin produit cadre
2. regles d'acces et parcours dans `docs/product/specification-lots-1-2.md`
3. architecture cible et lots 3-4 dans `docs/architecture/system-design-lots-3-4.md`
4. mockups dans `docs/ds/mockups/` pour la verite visuelle
5. present document pour les garde-fous d'implementation

Regle pratique :

- **les mockups font foi pour l'UI**
- **les specs font foi pour le comportement**
- **la doctrine fait foi pour les choix de structure**

## Contraintes confirmees

- DevGate est un **portail d'acces** a des environnements de dev / staging.
- Le portail est **brande agence uniquement**.
- La v1 repose sur un modele d'acces **par client**.
- Un utilisateur rattache a un client voit les ressources de ce client.
- Les ressources sont affichees directement dans la page client.
- Le login principal est de type **magic link** et/ou **OTP email**.
- Certaines ressources peuvent avoir leur propre auth applicative apres DevGate.
- Les serveurs de dev ne doivent pas etre exposes directement.
- Le navigateur utilisateur ne doit pas utiliser les hostnames Cloudflare bruts.
- Le cout d'exploitation doit rester maitrise.

## Stack retenue

- frontend web : `Next.js`
- backend : `FastAPI`
- base de donnees : `PostgreSQL`

## Hypothese d'architecture retenue

### Cible v1

Un **produit monolithique modulaire a deux applications** :

- une web app `Next.js`
- une API `FastAPI`

La web app porte :

- portail utilisateur
- back-office agence
- experience brandee

L'API porte :

- auth et session
- audit
- gateway reverse proxy
- API interne et admin
- integration Cloudflare

Autour du noyau :

- `PostgreSQL`
- provider email
- `Cloudflare Tunnel`
- `Cloudflare Access` utilise en **service auth** pour les upstreams

### Pourquoi

- c'est le plus sobre ;
- c'est coherent avec la taille de l'equipe et du produit ;
- c'est plus facile a deployer, debugger et faire evoluer ;
- les volumes cibles ne justifient pas une architecture distribuee.

### Trade-off assume

Le monolithe devient un composant critique.

Ce n'est pas un probleme en v1.  
Ce sera a revisiter si :

- le trafic augmente fortement ;
- le gateway devient trop complexe ;
- des equipes distinctes ont besoin de cycles de livraison differents.

## Principes structurants

### P1 - Monolithe modulaire, pas de microservices

Tout nouveau code doit entrer dans une structure modulaire interne claire.  
On n'extrait pas de service tant que le besoin n'est pas prouve.

`Next.js` et `FastAPI` ne sont pas a traiter comme des microservices.  
Ils forment une seule architecture produit avec deux runtimes.

### P2 - Le domaine produit pilote la structure

On structure d'abord par **capacite metier**, pas par type technique global.

Exemples de modules attendus :

- `auth`
- `portal`
- `clients`
- `resources`
- `audit`
- `gateway`
- `admin`
- `transport`

### P3 - Le front ne connait jamais Cloudflare

Le frontend ne manipule :

- ni service token ;
- ni hostname tunnel ;
- ni logique Cloudflare Access ;
- ni details d'upstream.

Tout cela reste dans le backend / gateway.

### P4 - DevGate controle l'entree

L'utilisateur entre toujours par DevGate.  
L'application cible peut ensuite demander sa propre auth, mais ne remplace pas DevGate comme porte d'entree.

### P5 - L'acces v1 reste par client

On n'introduit pas de permissions fines par ressource tant qu'un cas reel n'impose pas cette complexite.

### P6 - L'audit n'est pas un bonus

Tout flux critique doit produire des evenements auditables :

- login demande
- login consomme
- creation client
- creation utilisateur dans client
- creation ressource dans client
- connexion effective a une ressource

## Doctrine de decoupage

## Frontend

Le frontend doit etre organise par **surfaces produit**, pas par spaghetti de composants.

Stack cible :

- `Next.js`
- `React`
- `TypeScript`

Surfaces cibles :

- login
- portail
- page client
- detail ressource
- interstitiel double auth
- etats vide / expire / refuse
- profil
- back-office

Le frontend ne doit pas :

- embarquer de logique d'autorisation metier complexe ;
- dupliquer des regles serveur ;
- parser des objets techniques Cloudflare.

## Backend

Le backend porte :

- la source de verite des clients, users, ressources et grants ;
- la session ;
- les challenges de login ;
- l'audit ;
- la resolution des ressources ;
- l'appel vers l'upstream protege.

Stack cible :

- `FastAPI`
- `Python`

Le backend ne doit pas :

- melanger logique de transport et logique de presentation dans un meme fichier massif ;
- exposer des objets base de donnees bruts comme contrats d'API ;
- disperser l'audit dans du logging opportuniste.

## Gateway

Le gateway est une responsabilite backend distincte, meme s'il vit dans le meme deploiement.

Il doit etre traite comme une couche specifique avec ses propres regles :

- verification session
- verification des grants
- resolution resource -> upstream
- injection des credentials de service
- proxy HTTP propre
- gestion des erreurs upstream

Le gateway n'est pas :

- un detail de controller ;
- ni un ensemble de redirects improvisees.

## Doctrine de donnees

## Stockage

Choix de base :

- `PostgreSQL` des le depart

Pourquoi :

- sessions ;
- audit ;
- relations metier simples mais centrales ;
- administration multi-objets ;
- besoin de requetes fiables.

## Regles

- les migrations sont versionnees ;
- le schema suit le domaine, pas les ecrans ;
- les secrets ne deviennent pas une source de verite primaire en base ;
- les tables d'audit restent append-only autant que possible ;
- les suppressions dures doivent etre rares et explicites.

## Doctrine d'integration externe

Cloudflare est une **brique d'infrastructure**, pas le centre du produit.

### Regles

- le login user reste chez DevGate ;
- Cloudflare Access sert de barriere edge entre DevGate et l'upstream ;
- les credentials Cloudflare restent cote serveur ;
- le produit doit pouvoir fonctionner avec une configuration Cloudflare semi-assistee en v1 ;
- on n'automatise pas tout si la charge operative ne le justifie pas encore.

## Doctrine de securite

- cookies de session securises ;
- login sans mot de passe partage ;
- tokens de login a duree courte ;
- rate limiting sur demarrage de login ;
- aucune fuite de secret Cloudflare vers le navigateur ;
- aucune URL tunnel brute dans l'UI ;
- traitement explicite des etats refuses, expires et invalides.

## Doctrine UI

Les mockups dans `docs/ds/mockups/` sont la reference visuelle.

Regles :

- ne pas reinventer la navigation ;
- ne pas changer la hierarchie des ecrans sans impact produit assume ;
- ne pas introduire un style visuel generic system par paresse ;
- conserver le branding agence unique ;
- conserver une UX lisible pour des utilisateurs non techniques.

## Ce qui est volontairement hors doctrine v1

- microservices ;
- multi-agence complexe ;
- RBAC fin par ressource ;
- SSO corporate client ;
- provisioning Cloudflare full-auto obligatoire ;
- observabilite lourde ;
- event sourcing ;
- CQRS.

## Changement de doctrine

Une decision qui contredit ce document doit etre explicite.

Cas typiques qui meritent un ADR ou une note de decision :

- extraction d'un service ;
- introduction de permissions par ressource ;
- changement de stack de stockage ;
- passage de Cloudflare service auth a un autre modele ;
- ajout d'une seconde couche de personnalisation par client.

## Ce que je ferais a ta place

Je traiterais ce document comme le garde-fou principal pendant la construction :

- si un choix simplifie le build sans casser cette doctrine, on le prend ;
- si un choix semble "plus propre" mais complexifie fortement la v1, on le repousse.
