# Expression de besoin — Portail d'accès sécurisé aux environnements de développement

**Projet** : DevGate (nom de travail)
**Date** : 19 avril 2026
**Auteur** : [Nom de l'agence]
**Statut** : Draft v3 — enrichi après analyse licensing Pangolin

---

## 1. Contexte

L'agence développe et maintient des sites web pour ses clients. Chaque projet dispose d'un ou plusieurs environnements de développement / staging hébergés sur des serveurs dédiés (Hetzner ou équivalent).

Aujourd'hui, la sécurisation de ces environnements repose sur des solutions artisanales : `.htaccess` avec authentification basique, mots de passe partagés par email, ou absence pure et simple de protection. Cette situation génère des irritants récurrents :

- Mots de passe perdus ou partagés sans contrôle
- Oubli de protection sur un nouveau sous-domaine
- Aucune visibilité centralisée sur "qui a accès à quoi"
- Serveurs de dev exposés publiquement (scans, bots, indexation accidentelle)
- Friction côté client (VPN exclu, htaccess pénible)

## 2. Objectif

Mettre en place un système centralisé permettant de :

1. **Protéger** les environnements de développement du monde extérieur (idéalement : aucun port ouvert sur Internet)
2. **Authentifier** les clients de manière simple (sans mot de passe, sans VPN, sans installation)
3. **Gérer** les accès par projet depuis une interface d'administration côté agence
4. **Automatiser** le provisioning et le déprovisioning des accès

## 3. Personas

### Client (utilisateur final)

- Non technique
- Veut accéder au site de dev pour valider / recetter
- Ne veut rien installer, rien configurer
- Dispose d'une adresse email professionnelle

### Chef de projet / développeur (agence)

- Crée les projets et les environnements
- Gère les accès clients (ajout/retrait d'emails autorisés)
- Veut une vue d'ensemble de tous les projets et accès actifs

### Administrateur (agence)

- Configure l'infrastructure sous-jacente
- Gère les tunnels, le DNS, les policies globales

## 4. Besoins fonctionnels

### 4.1 Portail client

| Ref | Besoin | Priorité |
|-----|--------|----------|
| C01 | Le client accède à ses environnements via un lien unique | Must |
| C02 | L'authentification se fait par email (One-Time PIN / magic link) | Must |
| C03 | Le client ne voit que les projets auxquels il est autorisé | Must |
| C04 | Le cookie de session dure une durée configurable (ex : 7 jours) | Should |
| C05 | Support SSO corporate (Google Workspace, Microsoft 365) en option | Could |

### 4.2 Back-office agence

| Ref | Besoin | Priorité |
|-----|--------|----------|
| A01 | Créer un projet (nom, URL(s) de dev, description) | Must |
| A02 | Ajouter/retirer des emails autorisés par projet | Must |
| A03 | Vue d'ensemble de tous les projets avec statut des tunnels | Must |
| A04 | Provisioning automatique : création du tunnel + DNS + policy d'accès | Should |
| A05 | Déprovisioning automatique : suppression tunnel + DNS + policy | Should |
| A06 | Historique des connexions par projet (qui, quand) | Could |
| A07 | Groupes de clients (ex : "équipe marketing client X") | Could |

### 4.3 Infrastructure et sécurité

| Ref | Besoin | Priorité |
|-----|--------|----------|
| I01 | Les serveurs de dev ne doivent pas avoir de port ouvert sur Internet | Must |
| I02 | Le trafic passe par un tunnel chiffré (type Cloudflare Tunnel) | Must |
| I03 | Aucune donnée d'authentification n'est stockée côté agence (déléguée au provider) | Should |
| I04 | Les environnements non protégés ne sont pas accessibles même en connaissant l'URL | Must |

## 5. Architecture cible envisagée

```
┌──────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│              │     │                     │     │                  │
│   Client     │────▶│  Cloudflare Access  │────▶│  Cloudflare      │
│   (navigateur)│     │  (auth + policy)    │     │  Tunnel          │
│              │     │                     │     │                  │
└──────────────┘     └─────────────────────┘     └────────┬─────────┘
                                                          │
                                                          │ connexion sortante
                                                          │ (pas de port ouvert)
                                                          ▼
                                                 ┌──────────────────┐
                                                 │                  │
                                                 │  Serveur de dev  │
                                                 │  (Hetzner)       │
                                                 │                  │
                                                 └──────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  Back-office agence                                              │
│  - CRUD projets / accès                                          │
│  - Appels API Cloudflare (tunnels, DNS, policies)                │
│  - Dashboard de supervision                                      │
└──────────────────────────────────────────────────────────────────┘
```

## 6. Paysage des solutions identifiées

Une recherche approfondie (avril 2026) a permis d'identifier 4 familles de solutions et 7 options concrètes. Le détail est disponible dans le rapport de recherche associé (`research-captive-portal-inverse-oss.md`).

### Famille A — SaaS (non OSS)
- **Cloudflare Access + Tunnel** : gratuit < 50 users, zero port ouvert, API complète, mais trafic via Cloudflare (privacy)

### Famille B — Reverse proxy authentifié self-hosted
- **Authentik** : IdP complet, portail utilisateur avec liste d'apps, OIDC/SAML/LDAP, Docker-ready. Mais ports 80/443 restent ouverts.
- **Pomerium** : identity-aware reverse proxy, clientless, plus léger qu'Authentik. Pas de portail "liste d'apps" natif.
- **Authelia** : forward auth léger, performant, mais pas de portail utilisateur intégré.

### Famille C — Tunnel inversé self-hosted + auth intégrée (⭐ découverte clé)
- **Pangolin** : plateforme open source (AGPL-3) combinant tunnel WireGuard inversé + reverse proxy Traefik + auth intégrée + dashboard UI. C'est l'équivalent self-hosted le plus complet de Cloudflare Tunnel + Access. Un VPS relai (~4€/mois) + l'agent "Newt" sur les serveurs de dev. Pas de port ouvert côté serveur de dev. Gestion des users, orgs, rôles, resources — le tout dans un seul produit. Activement maintenu (dernière release : avril 2026).
- **frp + Caddy + Authentik** : combo custom faisable mais non intégré, plus de plomberie à maintenir.

### Famille D — Mesh VPN (écartée)
- **Headscale / NetBird / Firezone** : nécessitent un agent côté client → rédhibitoire pour des clients d'agence non techniques.

## 6bis. Grille de comparaison des options shortlistées

| Critère | Cloudflare Access+Tunnel | Pangolin | Authentik+Traefik | Pomerium |
|---------|--------------------------|----------|-------------------|----------|
| Port ouvert côté serveur dev | Non | Non | Oui (80/443) | Oui (80/443) |
| Portail "liste d'apps" | Oui | Oui | Oui | Non |
| Auth email OTP / magic link | Oui | Oui (PIN, password) | Oui (configurable) | Via IdP externe |
| SSO corporate | Oui | Oui (OIDC) | Oui | Oui |
| 100% self-hosted | Non | Oui | Oui | Oui |
| Open source | Non | AGPL-3 | Apache 2.0 | Apache 2.0 |
| Effort setup | Faible | Moyen | Moyen-élevé | Moyen |
| Coût infra | Gratuit | ~4€/mois (VPS relai) | Inclus dans infra existante | Inclus dans infra existante |
| API pour automatisation | Oui (complète) | En développement | Oui | Oui (YAML) |
| Protection DDoS | Oui (réseau CF) | Non | Non | Non |
| Souveraineté données | Non | Oui | Oui | Oui |

## 6ter. Focus Pangolin — Licensing et implications pratiques

### Les 3 éditions

| | Community (self-hosted) | Enterprise (self-hosted) | Cloud |
|---|---|---|---|
| Licence | AGPL-3 | Fossorial Commercial | SaaS |
| Prix | Gratuit | À partir de $449/an (~37€/mois) | À partir de $4/user/mois |
| Limites users/sites | Illimité | 25 users / 25 sites (Starter) | 5 users (Basic gratuit) |

### Ce que la Community Edition inclut déjà

2FA (TOTP), RBAC, IdP externe OIDC au niveau serveur, auto-provisioning users depuis IdP, API key access, Blueprints (config déclarative), geoblocking, OTP email sur les ressources publiques. Pas de limite de sites/users/domaines en self-hosted.

### Ce que la Community n'inclut pas (Enterprise requis)

- **Logs d'accès** (HTTP request, resource access, client connection, platform action, CSV export, SIEM)
- **Connecteurs IdP Azure AD et Google Workspace** (seul OIDC générique est en Community)
- **Security policies** : 2FA enforcement, session duration, password expiration, device posture, credential rotation, device approvals
- **Site provisioning keys** (provisioning automatisé)
- **Custom branding** (logo/couleurs via le dashboard)
- **SSH management**

### Analyse licensing (AGPL-3) — ce qui est forkable vs ce qui ne l'est pas

L'AGPL-3 donne tous les droits de modification et redistribution, y compris pour un usage réseau (SaaS). Concrètement :

- **Le branding (login, couleurs, logo) est du code front-end** — il est dans le repo AGPL, il est forkable et modifiable légalement. L'effort est un fork CSS/React one-shot, mais la maintenance diverge à chaque update upstream. La feature Enterprise "custom branding" est un confort (UI de configuration), pas un verrou technique.

- **Les features backend (logs, connecteurs IdP Azure/Google, security policies)** sont probablement dans du code séparé non inclus dans le repo Community (modèle dual-licensing classique type GitLab). Si c'est le cas, ces features ne sont pas forkables — il faudrait les recoder from scratch ou payer la licence Enterprise.

- **L'obligation AGPL** : si l'agence modifie le code et l'expose comme service (ce qui est le cas ici), elle doit rendre le code modifié disponible aux utilisateurs du service. En pratique, pour un usage interne agence avec quelques clients, le risque est faible et la contrainte gérable.

### Recommandation sur le licensing

Pour un POC / phase 1 : la Community Edition suffit largement (tunnel + auth + dashboard + OTP email).

Pour un usage production avec traçabilité des accès clients : la licence Starter Enterprise à ~37€/mois est le bon investissement — elle débloque les logs, les policies de session, et les connecteurs IdP corporate. C'est moins cher qu'une heure de dev par mois.

Le branding peut être géré par fork AGPL en phase 1, puis basculé sur la feature Enterprise si la maintenance du fork devient pénible.

## 7. Contraintes

- **Budget** : solution gratuite ou très faible coût (< 50 utilisateurs sur Cloudflare Access)
- **Maintenance** : minimale — pas d'infra auth à maintenir côté agence
- **Onboarding client** : zéro installation, zéro compte à créer
- **Compatibilité** : fonctionne sur tous navigateurs, mobile inclus
- **Données** : aucune donnée client sensible ne transite par le back-office agence

## 8. Hors périmètre (v1)

- Gestion de droits fins dans les sites de dev (lecture seule, commentaires, etc.)
- Intégration CI/CD (provisionner automatiquement à chaque déploiement)
- Monitoring applicatif des sites de dev
- Gestion de la facturation client liée aux environnements

## 9. Critères de succès

1. Un nouveau projet est accessible au client en moins de 5 minutes après création dans le back-office
2. Le client accède à son environnement en moins de 30 secondes (email OTP)
3. Un serveur de dev n'est pas découvrable par scan de ports
4. L'agence a une vue temps réel de tous les accès actifs
5. Le déprovisioning d'un accès est immédiat

## 10. Prochaines étapes

1. **POC Pangolin Community** : déployer Pangolin sur un VPS Hetzner (~4€/mois), configurer un tunnel avec Newt sur un serveur de dev existant, tester le flow OTP email avec un vrai client
2. **POC Cloudflare (comparatif)** : configurer un tunnel CF + Access sur le même projet pour comparer l'UX et l'effort
3. **Évaluation licensing** : vérifier dans le repo GitHub quelles features Enterprise sont réellement absentes du code Community vs simplement gated par un flag de licence
4. **Décision** : arbitrer entre Pangolin Community (+ fork branding), Pangolin Starter Enterprise, ou Cloudflare Access
5. **Déploiement** : migration progressive des projets existants
