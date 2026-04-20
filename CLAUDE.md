# CLAUDE.md - DevGate

Ce fichier sert de memo de travail projet pour les assistants qui vont implementer DevGate.

## TL;DR

Si tu dois faire un choix rapidement, prends celui-ci :

- **monolithe modulaire**
- **PostgreSQL**
- **frontend pilote par mockups**
- **backend source de verite**
- **gateway integre a l'app**
- **Cloudflare Tunnel + Access en service auth**
- **pas de microservices**
- **pas de permissions fines par ressource en v1**

## Produit a construire

DevGate n'est pas un simple proxy.

C'est un produit avec 4 blocs :

1. login simple
2. portail utilisateur
3. back-office agence
4. acces securise aux ressources via gateway

## Rappels produit stables

- branding agence uniquement
- navigation par client
- ressources affichees directement dans la page client
- login par magic link et/ou OTP
- auth applicative aval possible
- audit minimal obligatoire
- connexions effectives visibles cote agence

## Regles d'architecture

### Monolithe modulaire

Ne separe pas en services tant que ce n'est pas necessaire.

### Backend = verite

Le backend decide :

- qui a acces ;
- quelle ressource est resolue ;
- quelle session est valide ;
- quel upstream appeler ;
- quel evenement auditer.

### Frontend = parcours

Le frontend affiche :

- les ecrans ;
- les etats ;
- le guidage utilisateur ;
- les informations utiles.

Il ne doit pas porter :

- des secrets ;
- de logique Cloudflare ;
- des permissions deduites seules ;
- de la logique d'infrastructure.

### Gateway = couche explicite

Le gateway n'est pas un bricolage de controller.

Il faut garder claire la couche qui :

- verifie session et grant ;
- charge la config resource ;
- ajoute les credentials de service ;
- proxifie ;
- gere les erreurs upstream.

## Sources de verite

Considere les fichiers suivants comme la base :

- `docs/ds/mockups/`
- `product-spec-devgate-lots-1-2.md`
- `system-design-devgate-lots-3-4.md`
- `build-plan-devgate.md`
- `docs/architecture/architecture-doctrine.md`
- `docs/contributing/frontend-contribution.md`
- `docs/contributing/backend-contribution.md`

## Workflow recommande

Quand tu implementes une fonctionnalite :

1. verifier le mockup correspondant
2. verifier la regle produit correspondante
3. verifier si elle touche la doctrine d'architecture
4. coder dans le module metier adapte
5. ajouter ou mettre a jour les tests du flux critique

## Points a ne pas deriver

- pas de SSO corporate client en v1 ;
- pas de modele par ressource en v1 ;
- pas d'automatisation Cloudflare lourde par defaut ;
- pas d'admin IAM complexe ;
- pas d'abstraction prematuree des composants UI ;
- pas de logique "juste pour preparer plus tard" si elle complique le present.

## Qualite attendue

Une bonne contribution DevGate doit etre :

- simple a lire ;
- testable ;
- compatible avec les mockups ;
- compatible avec l'acces par client ;
- observable via audit minimum ;
- sans fuite de details Cloudflare vers le navigateur.

## Si un arbitrage est flou

Choisir dans cet ordre :

1. la solution la plus simple ;
2. la plus lisible ;
3. la plus reversible ;
4. celle qui retarde le moins la v1 ;
5. celle qui n'ouvre pas une dette securite.

## Quand s'arreter et remonter un point

Remonte le point avant de continuer si la demande implique :

- permissions fines par ressource ;
- nouvelle couche de personnalisation par client ;
- extraction d'un service ;
- changement de stockage principal ;
- remplacement du modele Cloudflare retenu ;
- contournement du gateway DevGate.
