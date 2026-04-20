---
status: draft
skill: decision
confidence_level: high
date: 2026-04-20
---

# ADR-001 — Autodiscovery / provisioning Cloudflare pour DevGate

## Recommandation

**Retenir l'option A : provisioning semi-auto avec réconciliation Cloudflare.**

En pratique :
- **DevGate reste la source de vérité produit**
- Cloudflare sert de **source de vérité technique secondaire**
- la découverte automatique existe, mais comme **inventaire technique / contrôle de dérive**
- l'activation d'un environnement reste **explicite** dans DevGate

## Pourquoi cette option

C'est l'option la plus cohérente avec la façon dont DevGate est déjà cadré :

- accès **par client**
- back-office agence comme centre d'admin
- besoin de traçabilité
- besoin de simplicité opérationnelle
- volonté d'éviter la magie fragile

Le problème des autres options, surtout l'autodiscovery pure, c'est qu'elles risquent de faire glisser la source de vérité métier vers Cloudflare.  
Or Cloudflare modélise des **tunnels** et des **apps Access**, pas tes objets métier `client / environnement / ressource`.

L'option A garde le bon ordre :

1. l'agence crée ou active un environnement dans DevGate
2. DevGate rattache ou choisit le transport Cloudflare
3. DevGate provisionne `Access + service token + DNS`
4. un job de sync vérifie ensuite l'état réel et les dérives

Donc :
- modèle produit propre
- bruit réduit
- meilleure auditabilité
- moins de surprises si l'infra change

## Trade-offs assumés

- On renonce à un effet "magique" totalement auto-découvert.
- On garde une étape d'assignation ou d'activation explicite dans DevGate.
- On accepte un peu plus d'UX back-office pour gagner en robustesse.
- On assume que Cloudflare n'est pas la source de vérité métier.

## Options évaluées

| Option | Solidité du modèle métier | Simplicité v1 | Risque opérationnel | Verdict |
|---|---|---|---|---|
| A — Provisioning semi-auto + réconciliation | Très bon | Bon | Faible à moyen | **retenu** |
| B — Autodiscovery avec objet intermédiaire | Bon | Bon | Moyen | écarté |
| C — GitOps / Terraform comme source infra | Très bon | Faible en v1 | Moyen | écarté |
| D — CLI / agent de déclaration explicite | Bon | Moyen | Moyen | écarté |

## Pourquoi les autres options ne gagnent pas

**Option B — Autodiscovery avec objet intermédiaire**  
C'est la meilleure alternative à A.  
Elle est saine techniquement, mais elle reste plus compliquée à expliquer et à opérer qu'un modèle où DevGate reste clairement maître de la création/activation.

**Option C — GitOps / Terraform**  
Très solide à terme, mais trop lourd pour la v1.  
On rajoute une couche infra supplémentaire alors que l'enjeu principal est encore de faire vivre le produit.

**Option D — CLI / agent déclaratif**  
Plus propre que l'autodiscovery pure dans certains contextes, mais moins fluide pour l'agence.  
On remplace une intégration API assez naturelle par une discipline opératoire plus fragile.

## Critères absents

- **Volume réel de tunnels hors DevGate sur le compte Cloudflare**  
  Impact : s'il y en a beaucoup, l'autodiscovery devient encore moins attractive.
- **Discipline ops réelle de l'agence**  
  Impact : si les opérateurs veulent absolument du "brancher et voir apparaître", l'option B remonte.
- **Niveau d'automatisation attendu en v1**  
  Impact : faible à moyen, ne change pas la reco principale.

## Niveau de confiance

**Élevé** — la décision suit directement la structure produit de DevGate et évite un piège classique : laisser le modèle infra dicter le modèle métier.

## Conclusion

**Ne pas retenir l'autodiscovery pure comme comportement principal.**

Construire :
- **DevGate comme source de vérité** — l'environnement est créé dans DevGate
- **Cloudflare comme couche de transport/protection** — le tunnel est un détail d'implémentation
- **Sync Cloudflare comme réconciliation technique** — statut, dérive, orphelins
- **Activation explicite dans DevGate** — l'opérateur déclenche le provisioning Access + token + DNS
