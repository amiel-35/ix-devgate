# DevGate — Checklist Go-Live

Document de référence avant chaque déploiement en production.

## Infrastructure

- [ ] PostgreSQL accessible depuis le backend (connection pool configuré)
- [ ] Migrations Alembic à jour : `alembic upgrade head` sans erreur
- [ ] Domaine principal configuré (DNS → serveur / load balancer)
- [ ] HTTPS actif sur le domaine principal (certificat TLS valide)
- [ ] `COOKIE_SECURE=true` dans la configuration production

## Secrets

- [ ] `DEVGATE_MASTER_KEY` généré et stocké hors repo (1Password / Vault / Doppler)
  - Générer : `python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"`
- [ ] `SESSION_SECRET_KEY` changé (valeur unique, longue, aléatoire)
- [ ] `CF_API_TOKEN` restreint aux permissions minimales (List/Create tunnels, Access, DNS)
- [ ] Aucune variable secrète dans les logs, les headers HTTP, ou les réponses API

## Cloudflare

- [ ] `CF_ACCOUNT_ID` et `CF_ZONE_ID` corrects (vérifier dans le dashboard CF)
- [ ] `CF_API_TOKEN` valide — tester avec `curl -H "Authorization: Bearer $CF_API_TOKEN" https://api.cloudflare.com/client/v4/user/tokens/verify`
- [ ] Au moins un tunnel `cfargotunnel.com` visible dans le dashboard CF avant la première sync

## Email

- [ ] Provider email configuré (`EMAIL_PROVIDER=smtp` ou `resend`)
- [ ] Test d'envoi effectué (magic link reçu sur une adresse réelle)
- [ ] `SMTP_FROM` ou adresse Resend vérifiée (pas de spam / rebond)

## Application

- [ ] `ENV=production` et `DEBUG=false`
- [ ] `FRONTEND_BASE_URL` pointe vers le domaine public (pas localhost)
- [ ] Tests backend passent intégralement : `pytest -q` → 0 failures
- [ ] Au moins un utilisateur admin (`kind="agency"`) créé en base
- [ ] Audit log vérifié : les événements `gateway.resource.accessed` apparaissent

## Sécurité minimale

- [ ] Rate-limiting actif sur `/auth/start` et `/auth/verify`
- [ ] Cookies `httponly=true`, `secure=true`, `samesite=lax`
- [ ] En-têtes de sécurité HTTP vérifiés (Content-Security-Policy, X-Frame-Options…)
- [ ] Logs sans données personnelles (emails, tokens, secrets)

## Opérations

- [ ] Monitoring en place (uptime, erreurs 5xx)
- [ ] Backup PostgreSQL configuré (snapshot quotidien minimum)
- [ ] Procédure de rollback documentée (restaurer snapshot + redéployer version précédente)
