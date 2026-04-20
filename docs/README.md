# Documentation DevGate

## Objet

Ce dossier centralise toute la documentation projet.

La regle simple :

- la doc produit vit dans `docs/product/`
- la doc architecture vit dans `docs/architecture/`
- la doc de contribution vit dans `docs/contributing/`
- les mockups de reference vivent dans `docs/ds/mockups/`
- la doc de planification vit dans `docs/planning/`
- la recherche et l'exploration vivent dans `docs/research/`
- les anciens artefacts gardes pour trace vivent dans `docs/archive/`

## Ordre de lecture recommande

### 1. Comprendre le besoin

- `docs/product/expression-de-besoin.md`
- `docs/product/cadrage.md`
- `docs/product/prd.md`

### 2. Comprendre le produit v1

- `docs/product/specification-lots-1-2.md`
- `docs/ds/mockups/`

### 3. Comprendre la cible technique

- `docs/architecture/target-architecture.md`
- `docs/architecture/system-design-lots-3-4.md`
- `docs/architecture/architecture-doctrine.md`

### 4. Comprendre comment construire

- `docs/planning/build-plan.md`
- `docs/contributing/frontend-contribution.md`
- `docs/contributing/backend-contribution.md`

## Fichiers canoniques

### Produit

- `docs/product/expression-de-besoin.md`
  Point de depart brut du besoin.
- `docs/product/cadrage.md`
  Clarification et arbitrages de cadrage.
- `docs/product/prd.md`
  Vue produit globale.
- `docs/product/specification-lots-1-2.md`
  Spec fonctionnelle du portail et du modele d'acces.

### Architecture

- `docs/architecture/target-architecture.md`
  Vision cible globale DevGate.
- `docs/architecture/system-design-lots-3-4.md`
  Design technique du gateway, back-office, audit et exploitation.
- `docs/architecture/architecture-doctrine.md`
  Regles d'architecture a respecter pendant l'implementation.

### Contribution

- `docs/contributing/frontend-contribution.md`
- `docs/contributing/backend-contribution.md`

### Design / UX

- `docs/ds/mockups/`
  Source de verite visuelle.

### Planification

- `docs/planning/build-plan.md`
  Ordre de build et phases de livraison.

### Recherche

- `docs/research/exploration-options.md`
  Exploration des options techniques initiales.

### Archive

- `docs/archive/mockups/mockup-devgate-lots-1-2.html`
  Ancien mockup de discussion conserve pour trace, non canonique.

## Sources de verite

Ordre de priorite recommande :

1. `docs/ds/mockups/` pour l'UI
2. `docs/product/specification-lots-1-2.md` pour le comportement produit portail
3. `docs/architecture/system-design-lots-3-4.md` pour la cible technique
4. `docs/planning/build-plan.md` pour l'ordre d'execution
5. `docs/architecture/architecture-doctrine.md` pour les garde-fous de structure

## Note de rangement

Les fichiers Markdown de travail ne doivent plus etre poses a la racine du repo, sauf :

- `README.md`
- `AGENTS.md`
- `CLAUDE.md`
- `LICENSE`

Tout le reste doit aller dans `docs/` ou dans les futurs dossiers de code.
