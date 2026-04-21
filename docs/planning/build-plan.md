# Build Plan - DevGate

## Statut

**v1 livrée — 2026-04-21**

Toutes les phases (1–7) sont implémentées. La Definition of Done v1 est intégralement satisfaite.

## Objet

Transformer les specs et les mockups de reference en plan de build executable.

Ce document part des bases suivantes :

- `docs/product/specification-lots-1-2.md`
- `docs/architecture/system-design-lots-3-4.md`
- `docs/ds/mockups/` comme reference visuelle prioritaire

Le but n'est pas de refaire la spec.  
Le but est de definir :

- dans quel ordre construire ;
- ce qui bloque quoi ;
- ce qui doit etre livrable a chaque etape ;
- ce qu'il faut volontairement laisser hors v1.

## Hypothese de delivery

Approche recommande :

- un **produit DevGate a deux apps** en v1 ;
- un **frontend `Next.js`** pour portail + back-office ;
- un **backend `FastAPI`** pour auth, API, audit et gateway ;
- un **gateway logique** integre au backend ;
- `PostgreSQL` comme stockage principal ;
- `Cloudflare Tunnel` pour le transport ;
- `Cloudflare Access` en service auth pour proteger les upstreams ;
- le navigateur utilisateur ne parle qu'a DevGate.

## Principes de sequencing

1. Construire d'abord le **coeur visible et testable localement**.
2. Ne brancher Cloudflare qu'une fois le modele produit et les flows stabilises.
3. Ne pas commencer par l'automatisation infra.
4. Rendre le back-office utile tot, mais sobre.
5. Garder la possibilite d'une mise en prod partielle avant l'automatisation complete.

## Vue d'ensemble

Le plan est decoupe en `7 phases`.

1. Fondations projet et modele de donnees
2. Authentification et session DevGate
3. Portail utilisateur
4. Back-office agence v1
5. Gateway et acces aux ressources
6. Integrations Cloudflare et supervision
7. Hardening, QA et mise en service

## Phase 1 - Fondations projet et modele de donnees

### Objectif

Poser une base code + data solide avant de brancher les vrais flux.

### A construire

- structure applicative initiale ;
- squelette `Next.js` ;
- squelette `FastAPI` ;
- configuration des environnements ;
- connexion `PostgreSQL` ;
- migrations initiales ;
- seed minimal ;
- modele de donnees coeur :
  - `clients`
  - `users`
  - `client_user_memberships`
  - `resources`
  - `resource_transport_configs`
  - `sessions`
  - `login_challenges`
  - `audit_events`
  - `resource_health_checks`

### Livrables

- web app qui demarre ;
- API qui demarre ;
- schema de base cree ;
- migrations versionnees ;
- donnees de demo suffisantes pour brancher le portail et le back-office ;
- conventions de code et structure de dossiers.

### Criteres de sortie

- les objets `client`, `user`, `resource` et `membership` existent ;
- la relation d'acces par client est implementable sans contournement ;
- l'app peut afficher des donnees de test stables.

### Risques a contenir

- sur-modeliser trop tot les permissions ;
- ouvrir des exceptions par ressource alors que la v1 est par client.

## Phase 2 - Authentification et session DevGate

### Objectif

Rendre le login simple operationnel, sans encore ouvrir les vraies ressources.

### A construire

- ecran `E01 Login` ;
- integration login `Next.js` -> `FastAPI` ;
- flow `magic link` ;
- flow `OTP` ;
- creation et consommation des `login_challenges` ;
- creation des `sessions` ;
- cookie de session ;
- ecrans d'etat :
  - `E02 Magic sent`
  - `E03 OTP`
  - `E09 Link expired`
  - `E10 Session expired`
  - `E11 Access denied`

### Audit minimum a brancher ici

- login demande ;
- magic link demande ;
- OTP demande ;
- challenge consomme ;
- login refuse ;
- session creee ;
- session terminee ou expiree.

### Livrables

- un utilisateur connu peut se connecter ;
- un utilisateur inconnu recoit une reponse propre ;
- la session est persistante ;
- les ecrans d'erreur principaux existent.

### Criteres de sortie

- le flow de login fonctionne de bout en bout sur environnement local ou test ;
- les evenements d'audit auth sont stockes ;
- aucun mot de passe local n'est necessaire.

### Dependances

- Phase 1 terminee.

## Phase 3 - Portail utilisateur

### Objectif

Livrer le coeur visible du produit cote client.

### A construire

- shell portail brande agence ;
- web app `Next.js` structuree par surfaces ;
- navigation par client ;
- liste des clients accessibles ;
- page client avec ressources directes ;
- fiche detail ressource ;
- ecrans :
  - `E04 Portal`
  - `E05 Client`
  - `E06 Detail env`
  - `E07 Interstitiel double auth`
  - `E08 Empty`
  - `E12 Profile`

### Regles a respecter

- branding agence uniquement ;
- acces par client ;
- une ressource visible si l'utilisateur est membre du client ;
- ressource avec auth applicative supportee sans chercher du SSO v1 ;
- les mockups dans `docs/ds/mockups/` font foi pour la structure et les etats UI.

### Livrables

- portail navigable avec donnees reelles ;
- page client exploitable ;
- detail ressource lisible ;
- ecran interstitiel quand une auth applicative est attendue ;
- page profil / session minimale.

### Criteres de sortie

- un utilisateur rattache a un client voit ses ressources ;
- un utilisateur sans ressource exploitable tombe sur un etat vide propre ;
- le portail est conforme a la reference visuelle.

### Dependances

- Phase 2 terminee.

## Phase 4 - Back-office agence v1

### Objectif

Permettre a l'agence d'exploiter le produit sans outillage externe.

### A construire

- ecran back-office de reference ;
- back-office web `Next.js` ;
- creation client ;
- creation utilisateur dans un client ;
- creation ressource dans un client ;
- liste des ressources ;
- vue audit minimale ;
- vue connexions effectives ;
- etat / sante simple des ressources.

### Perimetre volontairement limite

- pas de moteur IAM complexe ;
- pas de groupes avances ;
- pas de workflow de validation ;
- pas d'automatisation Cloudflare complete obligatoire dans cette phase.

### Audit minimum attendu

- creation client ;
- creation user dans client ;
- creation ressource dans client ;
- login demande ;
- challenge consomme ;
- connexion effective a une ressource.

### Livrables

- un admin agence peut gerer les objets v1 ;
- l'agence a une visibilite simple sur qui accede et sur quoi ;
- les operations critiques laissent une trace auditable.

### Criteres de sortie

- le back-office permet de faire vivre un client sans intervention DB manuelle ;
- l'audit est consultable ;
- la connexion effective est visible.

### Dependances

- Phases 1 a 3 terminees.

## Phase 5 - Gateway et acces aux ressources

### Objectif

Faire passer l'utilisateur de DevGate vers la ressource sans exposer directement l'upstream.

### A construire

- resolution d'une ressource depuis une URL DevGate ;
- gateway logique integre au backend `FastAPI` ;
- verification session + droit d'acces ;
- proxy HTTP vers l'upstream ;
- interstitiel si la ressource a sa propre auth ;
- gestion des erreurs upstream ;
- support cookies, redirects et headers propres ;
- base de support websockets si necessaire.

### Regles critiques

- le navigateur n'utilise jamais le hostname Cloudflare brut ;
- DevGate injecte les credentials de service vers Cloudflare ;
- les credentials Cloudflare ne reviennent jamais au navigateur ;
- un utilisateur non autorise tombe sur `403` propre cote DevGate.

### Livrables

- ouverture d'une ressource depuis le portail ;
- blocage d'un utilisateur sans droit ;
- propagation correcte des flux web standards ;
- experience acceptable sur les apps deja authentifiees.

### Criteres de sortie

- la navigation vers une ressource marche sur au moins 2 ressources reelles ;
- les redirects applicatifs ne cassent pas le parcours ;
- le comportement d'erreur est maitrisé.

### Dependances

- Phase 3 terminee ;
- Phase 4 suffisamment avancee pour gerer les ressources.

## Phase 6 - Integrations Cloudflare et supervision

### Objectif

Brancher proprement la couche transport/protection reelle et donner une visibilite minimale d'exploitation.

### A construire

- liaison des ressources aux configs de transport ;
- stockage des references Cloudflare utiles ;
- service tokens Access ;
- health checks simples ;
- vue statut ressource ;
- instrumentation minimale :
  - temps de reponse gateway
  - erreurs 5xx
  - refus upstream Access
  - ressource indisponible

### Niveau d'automatisation recommande en v1

- creation de la ressource dans DevGate ;
- rattachement semi-assiste a la config Cloudflare ;
- verification de sante automatisee ;
- pas de full provisioning Cloudflare obligatoire au premier passage.

### Livrables

- ressource reliee a un upstream Cloudflare protege ;
- health status visible dans l'admin ;
- logs suffisants pour debugger une panne simple.

### Criteres de sortie

- une ressource en prod-like fonctionne via Cloudflare ;
- un service token invalide ou absent est identifiable ;
- une ressource KO remonte comme KO.

### Dependances

- Phase 5 terminee.

## Phase 7 - Hardening, QA et mise en service

### Objectif

Rendre la v1 exploitable proprement.

### A couvrir

- tests unitaires critiques ;
- tests integration auth + portail + gateway ;
- smoke tests manuels sur les ecrans mockup references ;
- verification cookies et session ;
- verification audit ;
- limitation de debit sur login ;
- gestion des TTL des challenges ;
- securisation secrets ;
- procedure simple de backup DB ;
- checklist de mise en service.

### Livrables

- suite de tests minimum ;
- checklist go-live ;
- runbook incident simple ;
- documentation d'exploitation minimale.

### Criteres de sortie

- le login, le portail, l'ouverture ressource et l'audit sont verifies ;
- la perte d'un challenge ou l'expiration de session sont correctement gerees ;
- l'agence peut onboarder un premier client sans bricolage.

## Decoupage build recommande

### Sprint 0

- setup projet
- setup `Next.js`
- setup `FastAPI`
- DB
- migrations
- seeds
- base UI

### Sprint 1

- auth `magic link`
- auth `OTP`
- sessions
- ecrans d'etat auth

### Sprint 2

- portail utilisateur
- page client
- detail ressource
- profil
- etat vide

### Sprint 3

- back-office v1
- CRUD client / user / resource
- audit minimal

### Sprint 4

- gateway integre
- ouverture de ressource
- interstitiel double auth
- gestion erreurs upstream

### Sprint 5

- branchement Cloudflare
- service tokens
- health checks
- statut ressource

### Sprint 6

- hardening
- QA
- go-live

## Ordre de build ecran par ecran

1. `E01 Login`
2. `E02 Magic sent`
3. `E03 OTP`
4. `E09 Link expired`
5. `E10 Session expired`
6. `E04 Portal`
7. `E05 Client`
8. `E08 Empty`
9. `E06 Detail env`
10. `E12 Profile`
11. `E07 Interstitiel`
12. `E11 Access denied`
13. `Back-office`

## Ce qu'il ne faut pas lancer trop tot

- SSO corporate ;
- gestion fine par ressource ;
- provisioning Cloudflare full-auto ;
- groupes et roles avances ;
- branding multi-client ;
- microservices ;
- SIEM ou observabilite lourde.

## Definition of Done v1

La v1 est consideree comme livree si :

- un admin agence peut creer un client ;
- il peut y rattacher un utilisateur ;
- il peut y rattacher une ressource ;
- l'utilisateur peut se connecter par magic link ou OTP ;
- il voit son portail ;
- il ouvre une ressource via DevGate ;
- la ressource n'expose pas directement son origine ;
- la connexion effective est auditee ;
- l'agence peut diagnostiquer une ressource indisponible sans aller fouiller en base.

## Ce que je ferais a ta place

Je lancerais le build dans cet ordre :

1. `Phase 1 + Phase 2`
2. `Phase 3`
3. `Phase 4` en version sobre
4. `Phase 5`
5. `Phase 6` en semi-auto
6. `Phase 7`

La vraie erreur ici serait de commencer par Cloudflare ou par l'automatisation infra.  
Le bon axe est :

- d'abord le produit visible ;
- ensuite le passage vers la ressource ;
- ensuite seulement la couche d'exploitation plus automatisée.
