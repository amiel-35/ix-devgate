# AGENTS.md - DevGate

Instructions projet pour les agents intervenant dans ce repository.

## Contexte projet

DevGate est un portail d'acces securise a des environnements de dev / staging.

Le produit vise en v1 :

- un portail brande agence ;
- un acces **par client** ;
- un login simple via `magic link` et/ou `OTP email` ;
- une page client affichant directement les ressources ;
- un back-office agence sobre ;
- un gateway applicatif vers des ressources protegees par `Cloudflare Tunnel` + `Cloudflare Access` en service auth.

## Sources de verite

Ordre de priorite a respecter :

1. `docs/ds/mockups/` pour la verite visuelle
2. `product-spec-devgate-lots-1-2.md` pour les regles produit portail
3. `system-design-devgate-lots-3-4.md` pour la cible technique
4. `build-plan-devgate.md` pour l'ordre d'execution
5. `docs/architecture/architecture-doctrine.md` pour les garde-fous structurels
6. `docs/contributing/frontend-contribution.md`
7. `docs/contributing/backend-contribution.md`

## Regles non negociables

- Ne pas redecider la navigation si un mockup existe deja.
- Ne pas introduire de permissions fines par ressource en v1 sans demande explicite.
- Ne pas exposer les hostnames Cloudflare ni les tokens au frontend.
- Ne pas transformer la v1 en microservices.
- Ne pas sur-concevoir l'automatisation Cloudflare.
- Ne pas casser le principe : **le navigateur parle a DevGate, pas a Cloudflare**.

## Doctrine de build

- Favoriser un **monolithe modulaire**.
- Decouper le code par capacites metier, pas par fourre-tout technique.
- Garder distincts :
  - auth
  - portal
  - admin
  - resources
  - audit
  - gateway
  - transport

## Frontend

- Les mockups de `docs/ds/mockups/` sont la reference.
- Le frontend ne porte pas la verite des droits.
- Le frontend ne connait pas Cloudflare.
- Les etats vides, expires, refuses et double auth sont obligatoires.
- Le branding est agence uniquement.

## Backend

- Le backend porte :
  - la session
  - les grants
  - l'audit
  - la resolution des ressources
  - le proxy upstream
- `PostgreSQL` est le stockage de reference.
- L'audit minimal v1 est obligatoire sur les flux critiques.

## Quand produire de la doc

Si un choix change :

- la structure du monolithe
- la granularite des acces
- la place de Cloudflare
- ou la forme du gateway

alors documenter la decision avant de propager du code.

## Quand coder

Avant une implementation importante :

- verifier si un mockup existe ;
- verifier si la regle est deja dans la spec ;
- ne pas inventer un comportement si la doc le tranche deja.

## Ce qu'il faut challenger

Signaler explicitement si une demande :

- pousse vers une complexite v2/v3 ;
- contredit l'acces par client ;
- transforme Cloudflare en login principal ;
- introduit des secrets ou logiques infra cote browser ;
- augmente fortement le couplage.
