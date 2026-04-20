---
status: draft
skill: explorer
largeur: large
nb_options: 7
---

# Exploration — Résolutions techniques pour le portail d'accès sécurisé aux environnements de dev

## Options

### Option 1 — Cloudflare Access + Tunnel (SaaS)

- Description : utiliser Cloudflare Tunnel (connexion sortante depuis le serveur de dev) + Cloudflare Access (auth OTP email + policies par app). Un petit back-office agence pilote l'API Cloudflare pour le provisioning.
- Ce que ça rend possible : zero port ouvert, DDoS protection, setup en quelques minutes par projet, UX client parfaite (OTP email, navigateur seul), API complète pour automatisation.
- Ce que ça suppose ou requiert : domaine géré par Cloudflare, tout le trafic transite par Cloudflare (data tenancy), dépendance à un service tiers US, respect des CGU Cloudflare (interdiction d'utiliser les tunnels pour du streaming vidéo, etc.), développement d'un back-office custom pour la couche "gestion projets/clients".
- Statut : réaliste

### Option 2 — Pangolin (full self-hosted, tout-en-un)

- Description : déployer Pangolin sur un VPS relai (~4€/mois). Pangolin intègre dans un seul produit : tunnel WireGuard inversé (via l'agent "Newt"), reverse proxy Traefik, auth intégrée (users, rôles, orgs), dashboard UI, gestion des resources, Let's Encrypt automatique. L'agent Newt s'installe sur chaque serveur de dev (Docker ou binaire).
- Ce que ça rend possible : zero port ouvert côté serveur de dev, portail avec liste d'apps par user, auth par PIN/password, gestion multi-org et RBAC, CrowdSec intégrable pour la protection. Pas besoin de développer un back-office custom — le dashboard Pangolin fait le job. Souveraineté totale des données.
- Ce que ça suppose ou requiert : un VPS avec IP publique et ports 80/443/51820 ouverts, un domaine avec wildcard DNS, maintenance de l'instance Pangolin (updates Docker), le projet est jeune (AGPL-3, communauté en croissance mais pas encore aussi mature que Cloudflare). Pas de DDoS protection intégrée. L'API est encore en développement — moins stable que CF pour l'automatisation poussée. L'auth est plus basique qu'Authentik (pas d'OTP email natif, pas de SAML/LDAP).
- Statut : réaliste

### Option 3 — Authentik + Cloudflare Tunnel (hybride OSS + SaaS)

- Description : utiliser Authentik comme IdP et portail utilisateur (self-hosted), combiné avec Cloudflare Tunnel pour le transport. Authentik gère les users, les groupes, les accès par app (portail "liste d'apps"). Cloudflare Tunnel gère l'invisibilité des serveurs (zero port ouvert). L'auth Cloudflare Access est configurée pour déléguer à Authentik via OIDC.
- Ce que ça rend possible : portail riche (flows custom, MFA, passkeys, SSO corporate), zero port ouvert, le meilleur des deux mondes. Possibilité de migrer vers du full self-hosted plus tard en remplaçant CF Tunnel par Pangolin ou frp.
- Ce que ça suppose ou requiert : deux systèmes à maintenir (Authentik + CF), la configuration OIDC entre Authentik et CF Access est documentée mais pas triviale, le trafic transite toujours par Cloudflare pour le transport, Authentik consomme plus de ressources (Postgres + Redis + 2 containers).
- Statut : réaliste

### Option 4 — Authentik + Traefik (full self-hosted, sans tunnel)

- Description : déployer Authentik devant Traefik sur le même serveur que les sites de dev (ou sur un serveur dédié). Traefik forward auth vers Authentik. Les serveurs de dev ont leurs ports 80/443 ouverts sur internet mais toute requête non authentifiée est rejetée.
- Ce que ça rend possible : full OSS, portail utilisateur natif, SSO, MFA, OIDC/SAML, flows custom. Pas de dépendance externe. Cohérent avec un setup Coolify/Traefik existant.
- Ce que ça suppose ou requiert : les ports 80/443 sont ouverts — les serveurs sont visibles sur internet (scannables). La sécurité repose sur la solidité de Traefik + Authentik (surface d'attaque non nulle). Pas de protection DDoS. Firewall strict obligatoire. Chaque vhost doit être correctement protégé par forward auth (risque d'oubli). Authentik a eu plus de CVE qu'Authelia.
- Statut : réaliste

### Option 5 — Pomerium (reverse proxy zero trust, self-hosted)

- Description : déployer Pomerium comme identity-aware reverse proxy devant les sites de dev. Configuration YAML, intégration avec un IdP externe (Google, Azure AD, ou Authentik).
- Ce que ça rend possible : accès clientless (navigateur seul), vérification continue (pas juste au login), context-aware (device, IP, heure, géoloc), self-hosted, données ne transitent pas par un tiers. Plus simple à configurer qu'Authentik pour le cas d'usage "proxy devant des apps".
- Ce que ça suppose ou requiert : ports 80/443 ouverts (même limitation que option 4). Pas de portail "liste d'apps" natif — le client doit connaître l'URL de chaque site. Nécessite un IdP externe pour la gestion des utilisateurs (Pomerium ne stocke pas les users). Minimum 50 users sur les plans payants (enterprise features).
- Statut : réaliste

### Option 6 — frp + Caddy + Authentik (combo custom full OSS)

- Description : construire un stack maison : frp pour le tunnel inversé (agent sur serveur de dev → relai sur VPS), Caddy comme reverse proxy avec TLS automatique, Authentik pour l'auth et le portail. Le tout orchestré par du scripting custom.
- Ce que ça rend possible : full souveraineté, zero port ouvert côté dev, portail riche (Authentik), chaque brique est mature et bien documentée individuellement. Flexibilité maximale.
- Ce que ça suppose ou requiert : 3 systèmes à intégrer et maintenir, pas de documentation intégrée du combo, plomberie custom pour le provisioning (scripting API frp + API Authentik + config Caddy), plus de points de failure, temps de setup significatif. C'est ce que Pangolin a packagé dans un seul produit.
- Statut : réaliste mais coûteux en maintenance

### Option 7 — Développer un micro-produit maison

- Description : coder un petit service web (FastAPI/Next.js) qui : gère une liste de projets/clients/URLs, expose un portail client avec login (magic link email via Resend/Postmark), et pour chaque requête authentifiée, forward vers le site de dev via un tunnel SSH -R ou WireGuard.
- Ce que ça rend possible : UX parfaitement adaptée au use case agence, features exactement calibrées (pas de bloat IdP), possibilité d'en faire un produit/service vendu à d'autres agences, maîtrise totale du code.
- Ce que ça suppose ou requiert : du temps de développement non trivial, maintenance continue, réinvention de la roue sur les parties auth/tunnel/TLS qui sont résolues par les solutions existantes, risques de sécurité liés à un code auth maison. Possible en mode MVP mais probablement pas rationnel face à Pangolin ou CF.
- Statut : spéculatif

## Questions ouvertes révélées

1. **Quel niveau de protection réseau est réellement nécessaire ?** Pour des sites de dev d'agence (pas de données sensibles, pas de secrets), un reverse proxy authentifié avec ports ouverts (options 4-5) est-il suffisant, ou le zero port ouvert (options 1-3) est-il un vrai besoin ?

2. **Quelle est la maturité réelle de Pangolin pour un usage production multi-client ?** Le projet est jeune (explosion de popularité fin 2025), les retours sont enthousiastes mais sur des usages homelab. Quid de la stabilité avec 20+ sites de dev et 50+ clients ?

3. **L'API Pangolin est-elle assez stable pour automatiser le provisioning ?** Si l'agence veut un flow "nouveau projet → clic → tout provisionné", il faut une API fiable. C'est documenté comme "en développement".

4. **Le coût caché de la maintenance self-hosted est-il supportable ?** Une agence web n'est pas une boîte d'infra. Cloudflare absorbe toute la maintenance infra (TLS, DDoS, uptime du relai). En self-hosted, c'est un VPS de plus à surveiller.

5. **Y a-t-il un besoin de SSO corporate côté clients ?** Si certains clients de l'agence ont un Google Workspace ou Azure AD et veulent se loguer avec, ça écarte Pangolin (auth basique) et favorise Authentik ou CF.

6. **Pangolin + Authentik est-il combinable ?** Utiliser Pangolin pour le tunnel + Authentik comme IdP externe donnerait le meilleur des deux mondes (zero port ouvert + portail riche + SSO). La faisabilité de ce combo n'est pas documentée.
