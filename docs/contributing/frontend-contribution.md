# Contribution Frontend - DevGate

## Objet

Donner une ligne claire pour construire le frontend DevGate sans dette inutile.

Ce document s'applique :

- au portail utilisateur ;
- aux ecrans de login ;
- aux etats d'erreur ;
- au detail ressource ;
- au profil ;
- au back-office si la meme app front le porte.

## Sources de verite frontend

Ordre de priorite :

1. `docs/ds/mockups/`
2. `product-spec-devgate-lots-1-2.md`
3. `build-plan-devgate.md`
4. `architecture-doctrine.md`

Regle :

- si un ecran existe en mockup, on ne redecide pas sa structure au hasard ;
- si un point n'est pas tranche visuellement, on revient a la spec ;
- si la spec et le mockup divergent, on documente l'arbitrage avant de coder large.

## Principes frontend

### 1. Le frontend sert la comprehension

Le produit s'adresse a des utilisateurs non techniques.  
Le front doit donc privilegier :

- clarte ;
- lisibilite ;
- parcours courts ;
- textes explicites ;
- etats bien distingues.

### 2. La verite metier reste au backend

Le frontend affiche, guide et orchestre le parcours.  
Il ne doit pas devenir la source de verite sur :

- les droits ;
- la session ;
- la ressource resolue ;
- la logique Cloudflare ;
- l'audit.

### 3. Les etats vides et erreurs sont des ecrans de premier rang

Les ecrans suivants ne sont pas du polish, ils font partie du produit :

- lien expire ;
- session expiree ;
- acces refuse ;
- aucun acces utile ;
- auth applicative supplementaire.

## Surfaces a traiter comme modules UI

- `auth`
- `portal`
- `client-page`
- `resource-detail`
- `interstitial`
- `profile`
- `admin`
- `shared-ui`

Le but n'est pas d'imposer une arborescence exacte tout de suite.  
Le but est d'eviter :

- un dossier `components` fourre-tout ;
- des pages avec toute la logique inline ;
- des composants utilitaires qui deviennent des mini-frameworks.

## Regles de composition

- une page compose des blocs lisibles ;
- un bloc gere une responsabilite UI claire ;
- les composants partages restent sobres ;
- pas de sur-abstraction avant repetition reelle ;
- pas de hook custom juste pour "faire propre".

## Regles de state management

### Cote client

Autorise :

- etat local d'UI ;
- formulaires ;
- toggles ;
- chargement local ;
- feedback utilisateur.

Interdit ou a minimiser :

- copie durable du domaine metier serveur ;
- caches maison complexes ;
- autorisation derivee uniquement du front ;
- logique de session dispersee dans toute l'app.

### Recommendation

Le minimum viable est prefere :

- etat local simple ;
- un petit client API propre ;
- derive server-first des donnees importantes.

## Regles de routing

Le routing doit coller aux surfaces produit.

Exemples cibles :

- page login
- page portail
- page client
- page detail ressource
- page profil
- pages d'etat
- back-office

Le routing ne doit pas refleter :

- des objets Cloudflare ;
- des choix purement techniques ;
- des couches infra.

## Regles de design system

- partir des tokens visibles dans les mockups ;
- ne pas rebasculer sur une UI generique fade ;
- conserver un branding agence unique ;
- garder les contrastes et la lisibilite ;
- prevoir desktop et mobile des le depart ;
- garder des composants simples a maintenir.

### A eviter

- proliferation de variantes inutiles ;
- animation cosmetique non justifiee ;
- abstraction prematuree des layouts ;
- sur-usage de bibliotheques UI si elles tordent le produit.

## Accessibilite minimale attendue

- labels explicites ;
- focus visible ;
- navigation clavier correcte sur login et portail ;
- messages d'erreur lisibles ;
- semantics HTML correctes ;
- contrastes suffisants.

## Regles de copy UI

- ton sobre et rassurant ;
- vocabulaire non technique ;
- pas de jargon infra ;
- expliquer clairement la double auth quand elle existe ;
- toujours dire ce que l'utilisateur peut faire ensuite.

## Regles de tests frontend

Minimum attendu sur les surfaces critiques :

- rendu des etats principaux ;
- login flow nominal ;
- portail avec ressources ;
- etat vide ;
- acces refuse ;
- session expiree ;
- interstitiel double auth.

Les tests doivent verifier :

- le comportement visible ;
- pas seulement les details d'implementation.

## Checklist de contribution frontend

Avant merge :

- l'ecran est aligne avec le mockup de reference ;
- le texte est comprehensible pour un non-technique ;
- aucun element Cloudflare n'est expose en UI ;
- le front n'invente pas une regle metier ;
- les etats chargement / erreur / vide sont traites ;
- le responsive de base est acceptable ;
- l'accessibilite minimale est respectee.

## Ce qu'il ne faut pas faire

- inventer une navigation plus "framework native" que le produit ;
- coupler la page a la forme brute de la base ;
- embarquer de la logique de securite dans le browser ;
- introduire un state manager lourd sans preuve de besoin ;
- multiplier les couches de composants "design system" avant repetition reelle.
