# Contribution Backend - DevGate

## Objet

Donner les regles de construction du backend DevGate pour garder une base simple, lisible et robuste.

Stack retenue :

- `FastAPI`
- `Python`
- `PostgreSQL`

Ce document couvre :

- domaine metier ;
- auth et session ;
- admin ;
- audit ;
- gateway ;
- integration Cloudflare ;
- persistence.

## Sources de verite backend

Ordre de priorite :

1. `docs/architecture/system-design-lots-3-4.md`
2. `docs/product/specification-lots-1-2.md`
3. `docs/planning/build-plan.md`
4. `docs/architecture/architecture-doctrine.md`

## Doctrine backend

### 1. Monolithe modulaire

Le backend v1 est un monolithe modulaire.

Dans le produit global, il coexiste avec une web app `Next.js`, mais reste l'unique backend de reference.

On cherche :

- des modules nets ;
- des responsabilites lisibles ;
- peu de couplage transverse ;
- des interfaces simples entre modules.

On refuse :

- les services distribues improvises ;
- les couches artificielles sans benefice concret ;
- les fichiers "god service".

### 2. Le domaine avant le transport

Le backend doit d'abord modeliser :

- clients
- utilisateurs
- memberships
- ressources
- sessions
- login challenges
- evenements d'audit

La logique de transport Cloudflare vient **apres** ce domaine, pas a la place.

### 3. Une separation claire des responsabilites

Responsabilites distinctes a maintenir :

- `auth`
- `portal`
- `admin`
- `resources`
- `audit`
- `gateway`
- `transport`

Le gateway peut vivre dans le meme process, mais pas comme un detail cache d'un controller.

## Regles d'API

- les endpoints exposent des contrats applicatifs, pas des tables ;
- les noms doivent rester metier ;
- les erreurs doivent etre explicites ;
- les statuts HTTP doivent etre coherents ;
- les endpoints admin et user doivent etre separes proprement ;
- pas de fuite de details Cloudflare cote API publique.

## Regles auth et session

- pas de mot de passe partage ;
- `magic link` et/ou `OTP email` ;
- challenges a duree courte ;
- challenge consommable une seule fois ;
- session serveur claire ;
- cookie securise ;
- expiration et refus geres explicitement.

Le backend doit produire les evenements audit associes :

- login demande ;
- challenge consomme ;
- login refuse ;
- session creee ;
- session expiree ou terminee si tracee.

## Regles d'acces

- la v1 reste **par client** ;
- un utilisateur rattache a un client accede aux ressources de ce client ;
- pas d'exceptions fines par ressource sans decision explicite ;
- les utilisateurs agence sont un cas encadre, pas une excuse pour casser le modele.

## Regles audit

L'audit est un vrai objet produit.

Minimum attendu :

- creation client ;
- creation user dans client ;
- creation ressource dans client ;
- login demande ;
- login consomme ;
- connexion effective a une ressource.

Regles :

- evenements structures ;
- timestamp systematique ;
- acteur et cible quand connus ;
- payload de metadata raisonnable ;
- pas de dependence sur les seuls logs applicatifs pour reconstituer l'histoire.

## Regles gateway

Le gateway doit :

- verifier session et droit d'acces ;
- resoudre la ressource ;
- charger la config transport associee ;
- injecter les credentials de service Cloudflare ;
- proxifier proprement ;
- gerer redirects, cookies, websockets si necessaire ;
- distinguer les erreurs :
  - non autorise DevGate
  - ressource introuvable
  - upstream indisponible
  - credential Access invalide

Le gateway ne doit pas :

- renvoyer des credentials Cloudflare au navigateur ;
- se melanger a la logique d'admin ;
- devenir un morceau de code special case par ressource.

## Regles Cloudflare

Cloudflare est traite comme un adaptateur externe.

Regles :

- `Tunnel` pour le transport ;
- `Access` pour la protection edge machine-to-machine ;
- le login utilisateur reste chez DevGate ;
- les references techniques Cloudflare sont stockees proprement ;
- les secrets sont geres hors base comme source primaire.

En v1 :

- le semi-manuel est acceptable ;
- le full-auto n'est pas une obligation.

## Regles DB et migrations

- `PostgreSQL` des le depart ;
- migrations obligatoires ;
- pas de modification manuelle du schema comme workflow normal ;
- noms de tables et colonnes coherents avec le domaine ;
- index minimum sur les parcours critiques ;
- audit append-only autant que possible.

## Regles d'erreurs

Le backend doit preferer des erreurs :

- courtes ;
- actionnables ;
- observables ;
- differenciables.

Exemples de cas a traiter explicitement :

- email inconnu ;
- challenge expire ;
- session expiree ;
- acces refuse ;
- ressource sans transport configure ;
- upstream KO ;
- Access token invalide.

## Regles de tests backend

Minimum attendu :

- tests unitaires sur auth, grants et audit ;
- tests integration sur login -> session -> portail ;
- tests integration sur admin minimal ;
- tests integration sur resolution resource -> gateway ;
- tests des cas expires / refuses.

Les tests critiques doivent couvrir les invariables, pas seulement les helpers.

## Checklist de contribution backend

Avant merge :

- le code reste dans un module metier clair ;
- aucune logique Cloudflare n'est remontee au frontend ;
- l'audit est present si le flux est critique ;
- la migration DB existe si necessaire ;
- les erreurs sont explicites ;
- les tests minimum sont ajoutes ou mis a jour ;
- le changement ne casse pas la doctrine "acces par client".

## Ce qu'il ne faut pas faire

- introduire un microservice "parce que c'est plus clean" ;
- rajouter des roles fins sans besoin produit valide ;
- ecrire un gros service fourre-tout pour auth + admin + gateway ;
- stocker des secrets en clair comme reference primaire ;
- traiter l'audit comme du logging opportuniste ;
- brancher Cloudflare partout dans le code au lieu de le contenir.
