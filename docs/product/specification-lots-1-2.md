# Product Spec - DevGate - Lots 1 et 2

## Statut

Draft v1

## Decomposition retenue

Ce document couvre explicitement :

- **Lot 1 - Modele produit et regles d'acces**
- **Lot 2 - Parcours utilisateur et portail**

Il ne couvre pas encore en detail :

- la couche gateway / tunnel / protection edge ;
- le back-office d'exploitation avance ;
- le provisioning technique automatise ;
- l'observabilite detaillee.

Le choix de decomposition est volontaire :

- d'abord figer **qui voit quoi**
- puis figer **ce que vit l'utilisateur**
- avant de specifier plus finement la technique de transport et d'exploitation.

---

# spec

## 1. Objectif

Definir de facon exploitable :

- le modele d'acces v1 de DevGate ;
- la navigation utilisateur cible ;
- les regles fonctionnelles du portail ;
- le comportement attendu pour les parcours de login et d'acces aux ressources.

L'objectif de ces deux lots est de permettre au design, au produit et a l'engineering de commencer le travail sur le coeur visible du produit sans attendre la specification detaillee de toute la couche infra.

## 2. Faits de cadrage

### Faits stabilises

- le portail est **brande agence uniquement** ;
- la navigation est **par client** ;
- un utilisateur rattache a un client a acces aux ressources de ce client ;
- la page client affiche **directement les ressources** ;
- la v1 doit supporter un login simple de type **magic link** et/ou **OTP email** ;
- la v1 doit supporter le cas ou la ressource finale possede deja sa propre auth ;
- la v1 doit journaliser au minimum :
  - login demande,
  - login consomme,
  - creation client,
  - creation user dans client,
  - creation ressource dans client,
  - connexions effectives ;
- la cible court / moyen terme est de l'ordre de :
  - `50 a 75` utilisateurs,
  - `20 a 25` environnements / ressources.

### Hypotheses de travail

- magic link sera probablement le mode principal ;
- OTP email reste un fallback acceptable si le magic link n'est pas le seul mode retenu ;
- un modele d'acces strictement **par client** couvrira l'essentiel du besoin initial ;
- les utilisateurs agence auront un statut particulier, mais sans faire exploser le modele v1.

### Zones encore ouvertes

- faut-il afficher un **etat de disponibilite** des ressources aux utilisateurs finaux ;
- faut-il garder un fallback OTP en plus du magic link dans l'experience standard ;
- faut-il prevoir des exceptions d'acces par ressource tres tot, ou seulement plus tard ;
- faut-il afficher un niveau intermediaire par projet dans certains cas, meme si la v1 vise un acces direct aux ressources.

## 3. Scope detaille

## 3.1 Inclus

- page de login publique agence ;
- demarrage d'un login par email ;
- validation du login ;
- creation et maintien de session utilisateur ;
- portail personnel ;
- page client ;
- liste des ressources accessibles du client ;
- acces a une ressource ;
- distinction visuelle entre ressources si necessaire ;
- prise en charge du cas "auth applicative supplementaire";
- modele d'acces par client ;
- modelisation des objets produit necessaires aux lots 1 et 2.

## 3.2 Exclu de cette spec

- provisioning technique des tunnels ;
- gestion avancee du statut reseau des ressources ;
- automatisation complete de l'integration Cloudflare ;
- supervision detaillee ;
- IAM avance par groupe / domaine / policy fine ;
- exceptions d'acces par ressource ;
- personnalisation de l'experience par client.

## 4. Acteurs

### Client user

Utilisateur final invite a consulter une ou plusieurs ressources d'un client.

### Agency member

Utilisateur interne agence ayant vocation a gerer ou consulter plusieurs clients.

### Agency admin

Utilisateur interne avec capacite de gestion sur les clients, utilisateurs et ressources.

## 5. Regles fonctionnelles coeur

## 5.1 Regles de rattachement

### R1 - Rattachement utilisateur

Un utilisateur v1 est rattache a un **client**.

### R2 - Portee d'acces

Le rattachement a un client donne acces aux **ressources de ce client**.

### R3 - Granularite v1

La granularite d'acces v1 est **le client**.  
Le produit ne doit pas dependre d'exceptions par ressource pour etre utile en v1.

### R4 - Visibilite

Un utilisateur ne doit jamais voir dans le portail une ressource appartenant a un autre client que celui auquel il est rattache, sauf cas explicite d'utilisateur agence.

## 5.2 Regles de navigation

### R5 - Point d'entree

L'utilisateur arrive sur une page de login agence unique.

### R6 - Resultat du login

Apres login, l'utilisateur doit atteindre un portail DevGate qui l'oriente vers son client et ses ressources.

### R7 - Vue client

La vue client doit afficher **directement les ressources** accessibles, sans imposer un niveau intermediaire par projet dans la v1 standard.

### R8 - Acces aux ressources

Depuis la vue client, chaque ressource doit etre accessible en un nombre minimal d'etapes, avec une formulation explicite de ce qui est ouvert.

## 5.3 Regles d'experience

### R9 - Branding

Le portail doit refléter l'identite de l'agence via :

- logo ;
- nom ;
- couleurs ;
- background ;
- police ;
- ton visuel coherent.

### R10 - Lisibilite

Le portail doit paraitre comprehensible a un utilisateur non technique.

### R11 - Friction

Le produit doit minimiser :

- les mots de passe partages ;
- la confusion entre plusieurs URLs ;
- les demandes de support basiques pour "ou aller" et "comment me connecter".

## 5.4 Regles d'authentification

### R12 - Login simple

Le login doit fonctionner sans mot de passe partage.

### R13 - Session

Une fois authentifie, l'utilisateur doit beneficier d'une session lui evitant de se reconnecter a chaque clic dans le portail, dans une duree raisonnable pour l'usage de validation.

### R14 - Consommation du login

Un login demande puis consomme doit etre journalise comme tel.

## 5.5 Regles de coexistence avec auth applicative

### R15 - Double auth acceptee

Si une ressource a deja sa propre authentification, DevGate ne doit pas tenter de la remplacer en v1.

### R16 - Porte d'entree commune

DevGate controle l'acces a la ressource.  
L'application conserve ensuite sa propre logique d'auth interne si elle existe.

### R17 - Attente utilisateur

La v1 doit permettre au produit d'indiquer clairement, si necessaire, qu'une ressource peut demander une authentification supplementaire une fois ouverte.

## 5.6 Regles d'administration minimales liees aux lots 1 et 2

### R18 - Creation client

L'agence doit pouvoir creer un client.

### R19 - Creation utilisateur

L'agence doit pouvoir creer ou rattacher un utilisateur a un client.

### R20 - Creation ressource

L'agence doit pouvoir creer une ressource rattachee a un client.

### R21 - Effet fonctionnel attendu

Une fois client, utilisateur et ressource crees, l'utilisateur doit retrouver cette ressource dans sa vue client apres login.

## 6. Dependances

- service email transactionnel pour login ;
- couche session fiable ;
- future couche de routage vers les ressources ;
- modele de donnees coherent avec les choix "par client" et "agence uniquement".

## 7. Open areas

- affichage ou non d'un etat de disponibilite des ressources ;
- mode principal de login a figer ;
- modelisation exacte des utilisateurs agence multi-clients ;
- besoin ou non d'un premier niveau de tri ou regroupement visuel des ressources dans la page client.

## 8. Etat de specification

### Suffisamment specifie pour lancer

- design et wording du parcours de login ;
- design du portail et de la page client ;
- modelisation v1 client / user / ressource / acces ;
- criteres d'affichage et de visibilite du portail.

### Pas encore suffisamment specifie pour lancer seul

- le provisioning technique automatique ;
- la supervision d'exploitation ;
- les details complets du transport et du proxy.

---

# user_flows

## Flow 1 - Login standard

1. L'utilisateur arrive sur la page de login DevGate.
2. Il saisit son email.
3. Le systeme demarre un login simple.
4. L'utilisateur valide le login via le mecanisme retenu.
5. Le systeme cree une session.
6. L'utilisateur arrive sur son portail.

## Flow 2 - Acces a une ressource d'un client

1. L'utilisateur se connecte.
2. Il arrive sur sa vue client.
3. Il voit la liste des ressources accessibles.
4. Il choisit une ressource.
5. Le systeme ouvre la ressource.
6. Si l'application a une auth propre, l'utilisateur la rencontre ensuite.

## Flow 3 - Premier onboarding d'un utilisateur

1. Un membre agence cree un client.
2. Il cree ou rattache un utilisateur a ce client.
3. Il cree une ou plusieurs ressources dans ce client.
4. L'utilisateur recoit son premier acces.
5. Lors de son premier login, il retrouve directement les ressources du client.

## Flow 4 - Cas utilisateur sans acces utile

1. L'utilisateur se connecte correctement.
2. Aucune ressource active n'est actuellement visible pour lui.
3. Le portail doit lui indiquer une situation comprehensible, sans page vide ambigue.

## Flow 5 - Ressource avec auth applicative

1. L'utilisateur se connecte a DevGate.
2. Il choisit une ressource marquee comme protegee par une auth applicative.
3. DevGate lui ouvre la ressource.
4. L'application cible demande ensuite ses propres identifiants.

---

# inventaire_ecrans

## E1 - Login DevGate

Role :

- point d'entree public ;
- brand agence ;
- demarrage du login.

Contenu macro :

- logo ;
- nom ;
- message de reassurance ;
- champ email ;
- CTA principal ;
- message secondaire d'aide.

## E2 - Validation login

Role :

- confirmation qu'un lien ou code a ete envoye ;
- ou ecran de soumission OTP selon le mode retenu.

Contenu macro :

- rappel de l'email cible ;
- consigne simple ;
- possibilite de renvoyer ;
- message d'erreur si necessaire.

## E3 - Portail apres login

Role :

- point d'arrivee apres auth ;
- orientation vers la vue client pertinente.

Contenu macro :

- salutation simple ;
- client actif ou selection du client si cas multi-client agence ;
- acces a la page client ;
- eventuels raccourcis utiles.

## E4 - Page client

Role :

- ecran central de la v1 ;
- affiche directement les ressources accessibles du client.

Contenu macro :

- nom du client ;
- liste des ressources ;
- informations minimales de contexte pour chaque ressource ;
- CTA d'ouverture.

## E5 - Etat vide / sans ressource

Role :

- expliquer une situation sans acces ou sans ressource active visible.

Contenu macro :

- message clair ;
- contact / prochain pas ;
- pas de vide silencieux.

## E6 - Etat erreur login

Role :

- expliquer une tentative invalide ou expiree.

Contenu macro :

- message comprehensible ;
- possibilite de recommencer ;
- aucune explication technique brute.

## E7 - Etat "auth supplementaire attendue"

Role :

- informer qu'une ressource peut demander une auth applicative apres l'ouverture.

Contenu macro :

- indication sobre ;
- pas de promesse trompeuse de SSO.

---

# modele_donnees

## Objets fonctionnels necessaires aux lots 1 et 2

### Client

Usage :

- unite principale de navigation v1 ;
- unite principale de droits v1.

Attributs macro :

- identifiant ;
- nom ;
- slug ;
- statut ;
- metadonnees de presentation si necessaire.

### Utilisateur

Usage :

- personne qui se connecte au portail.

Attributs macro :

- identifiant ;
- email ;
- nom d'affichage ;
- type (`client`, `agence`) ;
- statut.

### Ressource

Usage :

- environnement ou point d'acces visible dans le portail.

Attributs macro :

- identifiant ;
- client de rattachement ;
- nom ;
- type ou nature ;
- statut ;
- indicateur "auth applicative requise" ;
- URL publique DevGate.

### Grant d'acces

Usage :

- formalise qu'un utilisateur a acces a un client.

Attributs macro :

- utilisateur ;
- client ;
- role ;
- date d'activation ;
- date de revocation si applicable.

### Session

Usage :

- maintient l'etat connecte de l'utilisateur.

### Challenge de login

Usage :

- trace et supporte la demande puis la consommation d'un magic link ou OTP.

### Evenement d'audit

Usage :

- trace les evenements minimaux imposes dans le cadrage.

## Relations fonctionnelles

- un client possede plusieurs ressources ;
- un utilisateur client est rattache a un client ;
- un utilisateur agence peut avoir un perimetre plus large ;
- un grant relie un utilisateur a un client ;
- une ressource appartient a un client ;
- une session appartient a un utilisateur ;
- un challenge de login appartient a un utilisateur ;
- un evenement d'audit peut viser un client, un utilisateur, une ressource ou un login.

---

# cas_limites

## CL1 - Email non reconnu

Le systeme ne doit pas exposer inutilement la structure interne des clients ou utilisateurs.

## CL2 - Login expire ou deja consomme

L'utilisateur doit pouvoir recommencer sans parcours confus.

## CL3 - Utilisateur rattache a un client sans ressource exploitable

Le portail doit afficher un etat comprehensible, pas une page vide.

## CL4 - Ressource avec auth applicative

Le produit ne doit pas laisser croire que l'auth DevGate remplacera automatiquement l'auth de l'application.

## CL5 - Utilisateur agence

Le comportement attendu pour les utilisateurs agence doit rester compatible avec la logique client, sans forcer des exceptions massives des lots 1 et 2.

## CL6 - Ressource temporairement indisponible

Si une ressource n'est pas disponible, le produit doit eviter un ressenti "bug silencieux".

## CL7 - Client avec beaucoup de ressources

La page client doit rester lisible si le nombre de ressources augmente, meme si la cible v1 reste moderee.

---

# criteres_acceptation

## CA1 - Login

- un utilisateur autorise peut demarrer un login sans mot de passe partage ;
- un login demande est journalise ;
- un login consomme est journalise ;
- une session est ouverte apres validation reussie.

## CA2 - Portail

- apres login, l'utilisateur arrive sur DevGate et non sur un outil tiers visible ;
- il accede a une vue rattachee a son client ;
- il voit directement les ressources de son client.

## CA3 - Visibilite

- un utilisateur ne voit pas de ressource hors de son client ;
- un utilisateur sans ressource exploitable voit un etat comprehensible.

## CA4 - Branding

- la page de login et le portail affichent le logo, le nom, les couleurs, le background et la police agence ;
- aucune personnalisation client n'est requise en v1.

## CA5 - Auth applicative coexistante

- une ressource peut s'ouvrir apres passage par DevGate puis demander sa propre auth ;
- ce comportement n'est pas considere comme un bug de la v1.

## CA6 - Administration minimale

- l'agence peut creer un client ;
- l'agence peut creer un utilisateur dans ce client ;
- l'agence peut creer une ressource dans ce client ;
- une fois ces objets en place, l'utilisateur retrouve la ressource apres login.

## CA7 - Audit minimal

- les evenements suivants existent dans l'audit v1 :
  - login demande,
  - login consomme,
  - creation client,
  - creation utilisateur dans client,
  - creation ressource dans client,
  - connexion effective a une ressource.
