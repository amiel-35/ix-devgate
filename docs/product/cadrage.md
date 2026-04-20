# Cadrage — DevGate

## Objectif

Clarifier le besoin reel avant de choisir une solution ou de produire une spec.

Le sujet n'est pas "faire un portail joli" ni "tester un outil".  
Le sujet est : **standardiser l'acces client aux environnements de dev/staging de l'agence avec une bonne securite, une UX simple, et une admin centralisee.**

## Besoin reformule

L'agence veut un systeme qui permette a des clients non techniques d'acceder a certains environnements de dev/staging via un navigateur, avec un login simple, sans installation, sans mot de passe partage, et avec une vue claire des environnements auxquels ils ont acces.

Ce systeme doit aussi permettre a l'agence de gerer facilement :
- quels utilisateurs ont acces a quels environnements ;
- l'ajout / retrait d'acces ;
- la visibilite globale sur les environnements exposes ;
- la reduction maximale d'exposition reseau cote **serveurs de dev**.

Le portail d'acces lui-meme peut etre expose sur Internet.  
La contrainte forte porte sur les **serveurs de dev**, qui doivent idealement ne pas etre directement exposes.

## Faits disponibles

- Le besoin vise en priorite les **serveurs de dev/staging**, pas la prod.
- Les utilisateurs finaux sont principalement des **clients non techniques**.
- Il y a une **forte preference** pour une **liste des environnements accessibles** apres login, plutot qu'une simple collection d'URLs.
- Le login attendu est un **login simple**, de type :
  - OTP email,
  - magic link,
  - passkey,
  - ou equivalent faible friction.
- Le **SSO corporate cote clients n'est pas un besoin**.
- Un SSO eventuel pour les utilisateurs internes de l'agence serait un bonus, pas une exigence.
- Le back-office agence peut etre :
  - soit un produit distinct,
  - soit une couche d'admin d'un produit existant.  
  Il n'y a **pas de preference ferme** a ce stade.
- Il y a une preference pour une **page de login customisee**, surtout pour l'image agence / aspect marketing.
- Le besoin est d'abord **interne a l'agence**.
- Une possibilite de packaging futur est ouverte, mais ce n'est **pas le cadre principal** aujourd'hui.
- La contrainte "aucun port ouvert sur Internet" s'applique aux **serveurs de dev**, et c'est **forcement souhaite**.

## Contraintes

- UX client tres simple.
- Pas d'installation cote client.
- Pas de VPN.
- Pas de mot de passe partage.
- Gestion centralisee.
- Reduction forte de l'exposition reseau des serveurs de dev.
- Budget et maintenance probablement contraints, meme si non re-precises ici.
- Le sujet doit rester sobre : pas de sur-conception inutile.

## Hypotheses de travail

- **Hypothese probable** : la meilleure UX cible est :
  1. page de login custom agence,
  2. authentification simple,
  3. page listant les environnements autorises,
  4. clic vers l'environnement.
- **Hypothese probable** : le vrai modele metier est :
  - utilisateur
  - client / organisation
  - projet
  - environnement
  - autorisation d'acces
- **Hypothese probable** : l'agence a surtout besoin d'un **socle reutilisable**, meme si ce n'est pas encore un produit commercial.
- **Hypothese fragile** : un outil existant avec une bonne couche d'admin pourrait suffire sans back-office custom.  
  C'est plausible, mais pas encore valide.

## Risques de malentendu

- Confondre "pas de port ouvert sur Internet" avec "aucune surface exposee du tout".  
  Ce n'est pas le sujet : le portail d'acces peut etre public ; la cible est de ne pas exposer directement les serveurs de dev.
- Confondre "login simple" avec "email OTP uniquement".  
  Le besoin est plus large : faible friction, pas une techno unique imposee.
- Confondre "admin centralisee" avec "obligation de developper un outil maison".  
  Ce n'est pas demande a ce stade.

## Options considerees a ce stade

### Option A — Utiliser un produit existant avec son admin natif

- Ce que ca couvre :
  - login,
  - liste d'environnements,
  - admin des acces,
  - eventuelle customisation.
- Ce que ca implique :
  - dependre du modele de l'outil,
  - accepter ses limites UX / branding / API.

### Option B — Utiliser un produit existant comme moteur + ajouter une surcouche legere

- Ce que ca couvre :
  - moteur technique deja pret,
  - admin/agencement adapte a l'agence,
  - branding plus maitrise.
- Ce que ca implique :
  - un peu de developpement,
  - synchronisation entre modele metier et outil sous-jacent.

### Option C — Construire un produit plus autonome

- Ce que ca couvre :
  - UX totalement maitrisee,
  - modele metier propre,
  - packaging futur plus simple.
- Ce que ca implique :
  - davantage de developpement,
  - plus de maintenance,
  - plus de responsabilite securite.

## Recommandation de cadrage

Le besoin est **assez cadre pour comparer serieusement des solutions**, mais **pas encore assez ferme pour ecrire une spec produit detaillee**.

Ce qui est stable maintenant :
- cible utilisateur ;
- niveau de friction acceptable ;
- preference pour une page listant les environnements ;
- contrainte forte sur la non-exposition directe des serveurs de dev ;
- absence de besoin SSO corporate client ;
- absence de preference ferme sur "outil existant vs surcouche vs produit distinct" ;
- organisation principale des acces **par client** ;
- branding v1 minimum : **logo, nom, couleur, background, police** ;
- audit v1 minimum : **login demande, login consomme, creation client, creation user dans le client, creation ressource dans le client, connexions effectives** ;
- portail **brande agence uniquement** ;
- navigation utilisateur **directement par ressource** ;
- gestion des acces v1 **strictement par client** ;
- hypothese d'echelle court terme : **50 a 75 utilisateurs** et **20 a 25 environnements** ;
- dependance fournisseur acceptable si le **cout reste maitrise**.

Ce qui reste a fermer avant production :
- veut-on une simple admin centralisee ou aussi un vrai **workflow de provisioning** automatise des la v1 ?

## Questions ouvertes

- Le login simple doit-il etre strictement unique pour tous les cas, ou faut-il garder un fallback entre **magic link** et **OTP** ?
- Faut-il afficher aux utilisateurs finaux un **etat de disponibilite** de la ressource (par exemple "disponible" / "indisponible"), ou reserver cette information a l'agence ?
- Veut-on une simple admin centralisee ou aussi un vrai **workflow de provisioning** automatise des la v1 ?

## Prochain pas recommande

Passer a un **document de decision comparatif tres court**, centre sur 3 sujets uniquement :
1. capacite a ne pas exposer les serveurs de dev ;
2. qualite de l'UX login + liste d'environnements ;
3. capacite d'admin centralisee sans lourdeur.

Autrement dit :  
le prochain livrable utile n'est pas une spec technique complete, mais un **arbitrage de solution** sur la base de ce cadrage.
