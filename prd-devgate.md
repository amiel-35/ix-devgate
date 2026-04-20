# PRD - DevGate

## Statut

Draft v1

## 1. Contexte et probleme

L'agence developpe et maintient plusieurs sites web pour ses clients.  
Chaque projet dispose d'un ou plusieurs environnements de developpement, de staging ou de preview.

Aujourd'hui, l'acces a ces environnements repose sur des mecanismes artisanaux :

- authentification basique partagee ;
- mots de passe envoyes ou transmis manuellement ;
- protections oubliees sur certains sous-domaines ;
- absence de vue centralisee sur les acces ;
- friction importante cote client.

Ce fonctionnement cree trois problemes produit :

1. **Probleme de securite**  
   Les environnements de dev peuvent etre visibles ou insuffisamment proteges.

2. **Probleme d'exploitation**  
   L'agence n'a pas de systeme centralise pour savoir qui a acces a quoi, ni pour ajouter ou retirer rapidement des acces.

3. **Probleme d'experience**  
   Les clients non techniques doivent acceder a des environnements de validation sans VPN, sans installation, sans parcours confus.

Le besoin reel n'est pas simplement de "mettre une auth devant des sites".  
Le besoin est de mettre en place un **portail d'acces gere**, reutilisable sur plusieurs projets, qui standardise la facon dont l'agence expose ses environnements non publics.

---

## 2. Objectif et vision

### Objectif produit

Permettre a l'agence de donner un acces simple, centralise et controle a ses environnements de dev/staging, tout en reduisant fortement l'exposition directe des serveurs de dev.

### Vision

DevGate doit devenir la **porte d'entree unique** des environnements de validation de l'agence.

Pour le client :

- une page de login simple et rassurante ;
- une experience brandee agence ;
- une liste claire des environnements auxquels il a acces ;
- un acces rapide sans friction technique.

Pour l'agence :

- une administration centralisee ;
- une gestion des acces comprehensible ;
- une reduction des oublis de protection ;
- un fonctionnement repetable d'un projet a l'autre.

### Outcome attendu

Le succes de DevGate ne se mesure pas au nombre de tunnels ou de pages admin construites.  
Il se mesure au fait que :

- les environnements de dev ne sont plus exposes de maniere artisanale ;
- les clients accedent plus facilement aux environnements autorises ;
- l'agence reprend le controle sur la gouvernance des acces.

---

## 3. Utilisateurs cibles

## 3.1 Client final

Profil :

- non technique ;
- utilise le portail pour consulter ou valider un environnement ;
- ne veut rien installer ;
- veut un parcours simple et comprehensible ;
- dispose generalement d'une adresse email professionnelle.

Besoins principaux :

- comprendre rapidement qu'il est au bon endroit ;
- se connecter sans mot de passe partage ;
- voir uniquement les environnements qui le concernent ;
- acceder au site de validation sans se perdre dans des URLs multiples.

## 3.2 Chef de projet / developpeur agence

Profil :

- cree les projets et les environnements ;
- gere les acces clients ;
- doit pouvoir donner et retirer un acces rapidement.

Besoins principaux :

- ajouter un environnement dans le systeme ;
- autoriser un ou plusieurs utilisateurs ;
- verifier ce qui est expose et a qui ;
- ne pas avoir a bricoler manuellement chaque nouveau cas.

## 3.3 Administrateur agence

Profil :

- supervise le systeme ;
- gere les reglages globaux et la couche infrastructure.

Besoins principaux :

- avoir une vue d'ensemble ;
- verifier l'etat de disponibilite des environnements publies ;
- maintenir une hygiene de securite et d'exploitation acceptable.

---

## 4. Portee du produit

## 4.1 Inclus dans la v1

La v1 de DevGate couvre :

- une page de login brandee agence ;
- une authentification simple a faible friction ;
- un portail listant les environnements accessibles a l'utilisateur ;
- une gestion des acces par environnement ;
- une administration centrale agence ;
- la reduction forte de l'exposition directe des serveurs de dev ;
- le support du cas ou l'application cible possede deja sa propre authentification interne.

## 4.2 Explicitememt hors perimetre v1

La v1 n'inclut pas :

- gestion fine des droits a l'interieur des applications de dev ;
- workflow de commentaires, annotations ou validation metier ;
- CI/CD complet ;
- monitoring applicatif avance ;
- facturation ;
- marketplace multi-agences ;
- SSO corporate client ;
- federation d'identite complexe ;
- IAM entreprise complet.

---

## 5. Exigences fonctionnelles

## 5.1 Acces utilisateur

### FR1 - Login simple

Le produit doit permettre a un utilisateur autorise de se connecter sans mot de passe partage, via un mecanisme de login simple et faible friction.

Exigence retenue :

- la v1 doit supporter un mode de login simple type magic link ou OTP email.

Hypothese :

- passkeys pourront etre pertinentes ensuite pour certains usages recurrents, surtout cote agence.

### FR2 - Portail utilisateur

Une fois connecte, l'utilisateur doit arriver sur une page **par client** qui presente les ressources accessibles de ce client.

Exigence retenue :

- la logique de navigation principale est **par client** ;
- un utilisateur rattache a un client a acces aux ressources de ce client ;
- la page client affiche **directement les ressources** accessibles ;
- la liste des environnements / ressources n'est pas un nice-to-have ; c'est un element central de l'experience.

### FR3 - Visibilite limitee

Un utilisateur ne doit voir que les ressources du client auquel il est rattache.

### FR4 - Acces a un environnement

Depuis le portail, un utilisateur doit pouvoir acceder a un environnement en un minimum d'etapes.

### FR5 - Coexistence avec auth applicative

Le produit doit supporter le cas ou l'application de dev a deja sa propre authentification interne.

Effet attendu :

- DevGate controle l'entree dans l'environnement ;
- l'application conserve, si besoin, sa propre auth metier.

## 5.2 Administration agence

### FR6 - Gestion des projets et environnements

L'agence doit pouvoir creer et gerer des projets et leurs environnements associes.

### FR7 - Gestion des acces

L'agence doit pouvoir :

- creer un client ;
- creer un utilisateur dans un client ;
- creer une ressource dans un client ;
- ajouter ou retirer un acces a l'echelle du client ;
- connaitre les environnements exposes et les acces actifs.

### FR8 - Vue centralisee

L'agence doit disposer d'une vue d'ensemble des environnements publies et de leur statut global.

### FR9 - Branding agence

Le point d'entree utilisateur doit porter l'identite visuelle de l'agence au minimum via :

- logo ;
- nom ;
- couleurs ;
- background ;
- police ;
- presentation coherent avec l'image agence.

Exigence retenue :

- le portail est **brande agence uniquement** en v1 ;
- il n'est pas personnalise par client en v1.

### FR10 - Workflow sobre

Le produit doit reduire le nombre d'actions manuelles a effectuer pour exposer un environnement ou autoriser un utilisateur.

Hypothese :

- un provisioning partiellement manuel reste acceptable en v1 si l'usage quotidien est nettement simplifie.

## 5.3 Gouvernance et securite

### FR11 - Environnements non directement exposes

Les serveurs de dev ne doivent pas etre directement exposes sur Internet via des ports entrants publics classiques.

### FR12 - Controle d'acces obligatoire

Un environnement ne doit pas etre atteignable librement par simple connaissance de l'URL publique.

### FR13 - Historique minimal

La v1 doit fournir une forme minimale de tracabilite sur :

- les demandes de login OTP / magic link ;
- les consommations effectives de login OTP / magic link ;
- la creation d'un client ;
- la creation d'un utilisateur dans un client ;
- la creation d'une ressource dans un client ;
- les connexions effectives aux ressources.

Hypothese a confirmer :

- le niveau exact d'audit au-dela de ce minimum n'est pas encore totalement ferme.

---

## 6. Exigences non fonctionnelles

## 6.1 Experience utilisateur

- parcours clair ;
- login simple ;
- compatibilite navigateur desktop et mobile ;
- pas d'installation locale ;
- pas de VPN ;
- ressenti "portail agence" plutot que "outil technique brut".

## 6.2 Securite

- forte reduction de l'exposition reseau des serveurs de dev ;
- controle d'acces centralise ;
- absence de mot de passe partage ;
- isolation entre environnements selon les droits accordes.

## 6.3 Exploitation

- systeme administrable par une petite equipe ;
- maintenance raisonnable ;
- debuggage possible sans architecture lourde ;
- capacite a monter progressivement en robustesse ;
- cout global de la couche externe de transport / protection qui reste maitrise.

## 6.4 Evolutivite

Le produit doit pouvoir evoluer plus tard vers :

- plus d'automatisation ;
- un meilleur audit ;
- un packaging eventuel ;
- des usages plus recurrents ou plus larges.

Cela reste une **intention d'evolution**, pas une exigence v1.

---

## 7. Dependances et contraintes

## 7.1 Contraintes produit

- DevGate est d'abord un produit **interne a l'agence** ;
- un futur packaging reste possible, mais n'est pas la cible primaire ;
- le self-hosted total n'est pas une obligation ;
- le branding login / portail est important ;
- le SSO corporate client n'est pas prioritaire ;
- la dependance a un fournisseur externe est acceptable si le cout reste maitrise.

## 7.2 Dependances externes probables

- un fournisseur email transactionnel ;
- une brique de transport securisee de type tunnel ;
- un mecanisme de protection de l'entree vers les environnements ;
- un stockage des donnees produit et des sessions.

Le choix exact de ces briques ne change pas le PRD tant que les exigences produit ci-dessus sont tenues.

---

## 8. Metriques de succes

## 8.1 Metriques principales

1. **Temps d'ouverture d'acces**
   - un nouvel environnement doit pouvoir etre rendu accessible rapidement apres demande ou creation.

2. **Temps d'acces utilisateur**
   - un utilisateur autorise doit pouvoir acceder a son environnement en moins de quelques dizaines de secondes.

3. **Reduction des expositions involontaires**
   - baisse du nombre d'environnements exposes sans controle d'acces central.

4. **Visibilite agence**
   - l'agence doit pouvoir repondre rapidement a : "qui a acces a quoi ?"

5. **Temps de retrait d'acces**
   - un acces retire doit cesser d'etre utilisable quasi immediatement.

6. **Trajectoire de cout acceptable**
   - le cout de la couche de transport / protection doit rester compatible avec une cible d'environ `50 a 75 utilisateurs` et `20 a 25 environnements`.

## 8.2 Signaux qualitatifs

- moins d'echanges manuels de mots de passe ;
- moins de confusion cote client ;
- moins de sous-domaines oublies ou mal proteges ;
- meilleure perception de professionnalisme cote client.

---

## 9. Hypotheses critiques et risques

## 9.1 Hypotheses critiques

### H1 - Le login simple suffit

Hypothese :

- un parcours magic link / OTP email suffit pour la majorite des clients.

Ce n'est pas encore une validation terrain.

### H2 - Le portail avec liste d'environnements est la bonne UX

Hypothese :

- une navigation **par client** avec liste des ressources du client est preferable a un partage d'URLs isolees.

Cette hypothese est fortement probable, mais merite d'etre verifiee sur usage reel.

### H3 - Une administration centralisee reduit vraiment la charge

Hypothese :

- l'agence gagnera du temps et de la fiabilite avec un point d'administration unique.

### H4 - Le niveau de branding attendu est leger

Hypothese :

- logo + couleurs + presentation propre suffisent pour la v1.

Si l'attente reelle est une experience white-label bien plus poussée, le perimetre changera.

### H5 - Le modele d'acces par client suffit en v1

Hypothese :

- un rattachement utilisateur -> client suffit pour couvrir l'essentiel du besoin initial, sans exceptions par ressource en v1.

## 9.2 Risques

### R1 - Risque de sous-estimer l'audit

Si l'agence a besoin rapidement de savoir non seulement qui est autorise, mais qui s'est effectivement connecte et quand, la v1 devra integrer plus de tracabilite que prevu.

### R2 - Risque de double auth mal vecue

Certains environnements auront une auth DevGate puis une auth applicative.  
Cela est acceptable fonctionnellement, mais peut etre percu comme une friction supplementaire.

### R3 - Risque de derive fonctionnelle

Le produit pourrait glisser trop vite vers :

- IAM complexe ;
- portail multi-tenant lourd ;
- couche de provisioning complete ;
- produit commercial complet.

La v1 doit rester sobre.

### R4 - Risque de confusion entre produit et implementation

Le produit ne doit pas etre defini par une techno particuliere.  
La cible reste :

- acces simple ;
- administration centralisee ;
- serveurs de dev non exposes directement ;
- portail brandable.

---

## 10. Questions ouvertes

## Questions ouvertes produit

- Faut-il afficher aux utilisateurs finaux un **etat de disponibilite** des ressources, ou reserver cette information a l'agence ?

## Questions ouvertes business / exploitation

- La cible de `50 a 75 utilisateurs` et `20 a 25 environnements` doit-elle etre consideree comme la cible produit des 12 premiers mois, ou seulement comme une estimation de depart ?
- Quel niveau d'automatisation est indispensable en v1 pour que le gain soit reel ?
- Quel niveau de cout mensuel est considere comme "maitrise" pour la couche de transport / protection ?

---

## 11. Points a valider avant de passer en spec

Avant de passer a une spec produit / design / engineering detaillee, il faut valider :

1. **Le parcours de login cible**
   - magic link ;
   - OTP email ;
   - fallback si besoin.

2. **Le niveau minimal de branding**
   - logo ;
   - nom ;
   - couleurs ;
   - background ;
   - police.

3. **Le niveau minimal d'audit**
   - demandes OTP / magic link ;
   - consommations OTP / magic link ;
   - creation client ;
   - creation user dans client ;
   - creation ressource dans client ;
   - connexions effectives.

4. **Le niveau d'automatisation vraiment attendu en v1**
   - simple administration centralisee ;
   - ou provisioning/deprovisioning plus ambitieux.

5. **Le niveau de granularite des acces**
   - strictement par client ;
   - ou exceptions par ressource si necessaire.

6. **La visibilite du statut des ressources**
   - visible cote utilisateur ;
   - ou reservee a l'agence.

---

## 12. Conclusion

DevGate est un produit de **gouvernance d'acces aux environnements de dev/staging**.

Sa promesse n'est pas de devenir un IAM generaliste ni un simple proxy technique.  
Sa promesse est de donner a l'agence une facon propre, coherente et reutilisable de :

- proteger ses environnements non publics ;
- offrir un acces simple a des clients non techniques ;
- centraliser l'administration des acces ;
- renforcer son niveau de controle et de professionnalisme.

Le succes de la v1 dependra moins de la richesse fonctionnelle brute que de sa capacite a tenir quatre promesses simples :

- login facile ;
- liste claire des environnements ;
- administration centralisee ;
- serveurs de dev non exposes directement.
