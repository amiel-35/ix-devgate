<original_task>
Compléter la v1 de DevGate en exécutant les plans Phase 6 (intégration Cloudflare) et Phase 7 (hardening/go-live) déjà écrits, puis identifier et livrer les chantiers restants pour atteindre la Definition of Done v1 du build plan.
</original_task>

<work_completed>
## Contexte de session

Cette session est une continuation d'une session précédente où les plans Phase 6 et Phase 7 avaient été écrits et exécutés (117 tests, mergés sur main). La session a démarré avec la question "c'est quoi les chantiers restants ?" et s'est terminée avec la v1 entièrement livrée.

---

## Plans écrits (3 nouveaux plans)

### `docs/superpowers/plans/2026-04-21-resource-health-ui.md`
Afficher le statut de santé upstream (online/offline/unknown) dans le back-office admin.
- Task 1 : enrichir `GET /admin/environments` avec `health_status` + `health_latency_ms` via sous-requête SQLAlchemy sur `TunnelHealthSnapshot`
- Task 2 : colonne "Santé" + bouton "Tester" dans `EnvironmentsClient.tsx`

### `docs/superpowers/plans/2026-04-21-gateway-instrumentation.md`
Rendre visible l'activité gateway (latence, erreurs).
- Task 1 : enrichir l'audit `gateway.resource.accessed` avec `latency_ms`, `is_5xx`, `is_cf_refused` + créer `gateway.request.failed` pour les upstream KO
- Task 2 : endpoint `GET /admin/gateway-stats` agrégeant les 24 dernières heures
- Task 3 : widget 6 cartes dans le dashboard admin

### `docs/superpowers/plans/2026-04-21-runbook-exploitation.md`
Document `docs/runbook-exploitation.md` — 5 scénarios d'incident.

---

## Implémentation exécutée (3 agents en parallèle)

### Plan 1 — Resource Health UI (agent Sonnet, branch feature/resource-health-ui)

**`apps/api/app/modules/admin/router.py`** — `list_environments()` enrichie :
- Import ajouté : `TunnelHealthSnapshot`
- Sous-requête SQLAlchemy groupée pour récupérer le dernier snapshot par env en O(1) requête
- Champs ajoutés dans la réponse : `health_status` (str|None), `health_latency_ms` (int|None)

**`apps/api/tests/integration/test_admin_router.py`** — 2 nouveaux tests :
- `test_list_envs_health_status_null_when_no_snapshot`
- `test_list_envs_health_status_reflects_latest_snapshot`
- Helper `_make_health_snapshot()` ajouté

**`apps/web/src/lib/api/server-admin.ts`** — `AdminEnvItem` enrichi :
- `health_status: "online" | "offline" | "unknown" | null`
- `health_latency_ms: number | null`

**`apps/web/src/lib/api/client.ts`** — ajout dans `adminApi.environments` :
- `ping(envId)` → `POST /admin/environments/{envId}/ping`

**`apps/web/src/app/(admin)/admin/environments/EnvironmentsClient.tsx`** — refonte partielle :
- Composant `HealthBadge` (badge coloré online=vert, offline=rouge, unknown=orange)
- State `pingStates: Record<string, PingState>`
- Handler `handlePing(envId)` — appelle le ping et met à jour l'état local
- Nouvelle colonne "Santé" dans le tableau (6e colonne, colSpan ajusté)
- Bouton "Tester" par ligne (réutilise `styles.btnSecondary` + overrides inline)

### Plan 2 — Gateway Instrumentation (agent Sonnet, branch feature/gateway-instrumentation)

**`apps/api/app/modules/gateway/service.py`** — `proxy_request()` modifiée :
- `import time` ajouté
- `start = time.monotonic()` avant l'appel httpx
- `latency_ms = int((time.monotonic() - start) * 1000)` après
- Audit `gateway.resource.accessed` enrichi : `latency_ms`, `is_5xx` (bool), `is_cf_refused` (bool, status==403)
- Blocs `except httpx.ConnectError` et `except httpx.TimeoutException` : ajout d'un `audit(..., event_type="gateway.request.failed", metadata={"reason": "upstream_unavailable"|"timeout"})` + `db.commit()` avant re-raise

**`apps/api/app/modules/admin/router.py`** — nouveau endpoint `GET /admin/gateway-stats` :
- Filtre `gateway.resource.accessed` et `gateway.request.failed` sur les 24 dernières heures
- `total_requests = len(accessed) + upstream_unavailable_count`
- Calcul avg et p95 latence en mémoire Python
- Retourne : `{since_hours, total_requests, errors_5xx, cf_refused, upstream_unavailable, avg_latency_ms, p95_latency_ms}`

**`apps/api/tests/integration/test_gateway.py`** — 4 nouveaux tests :
- `test_gateway_audit_includes_latency_ms`
- `test_gateway_audit_marks_5xx`
- `test_gateway_audit_marks_cf_refused`
- `test_gateway_unavailable_creates_failed_audit_event`

**`apps/api/tests/integration/test_admin_router.py`** — 2 nouveaux tests :
- `test_gateway_stats_empty`
- `test_gateway_stats_counts_events` (total_requests=5 : 4 accessed + 1 failed)

**`apps/web/src/lib/api/server-admin.ts`** — ajouts :
- Type `GatewayStats` exporté
- `serverAdminApi.gatewayStats()` → `GET /admin/gateway-stats`

**`apps/web/src/app/(admin)/admin/page.tsx`** — dashboard enrichi :
- Import `GatewayStats`
- `gatewayStats` chargé en parallèle avec `stats` et `events` via `Promise.all`
- Section "Gateway — 24 dernières heures" avec grille de 6 statCards

### Plan 3 — Runbook (agent Haiku, branch feature/runbook-exploitation)

**`docs/runbook-exploitation.md`** créé — 258 lignes, 5 incidents :
1. Ressource indisponible (502) — ping + vérif tunnel CF + logs
2. 403 service token invalide — audit query + regen token CF + PUT service-token
3. Provisioning en échec — lecture job state + diagnostic par état + rejouer activate
4. Boucle session expirée — vérif session en base + horloge NTP + TTL
5. Migration Alembic bloquée — alembic current/history + upgrade head + stamp d'urgence

### Résolution de conflit lors du merge

Plans 1 et 2 touchaient tous deux `test_admin_router.py` (ajouts à la fin du fichier). Conflit résolu manuellement en conservant les deux blocs de tests dans l'ordre : health_status tests (plan 1) puis gateway-stats tests (plan 2).

### Finalisation

- Merge séquentiel des 3 branches sur `main` : runbook (sans conflit) → health-ui (sans conflit) → gateway-instrumentation (conflit résolu)
- 3 worktrees supprimés, 3 branches feature supprimées
- **125 tests passants** après merge complet
- `docs/planning/build-plan.md` statut mis à jour : `Draft v1` → `v1 livrée — 2026-04-21`
- Commit final : `docs: build-plan — marquer v1 livrée (2026-04-21)`
</work_completed>

<work_remaining>
## Rien — la v1 est livrée.

La Definition of Done v1 du build plan est intégralement satisfaite :

| Critère | Statut |
|---|---|
| Admin peut créer un client | ✅ |
| Rattacher un utilisateur | ✅ |
| Rattacher une ressource | ✅ |
| Login magic link ou OTP | ✅ |
| Portail utilisateur visible | ✅ |
| Ouverture ressource via DevGate | ✅ |
| Origine non exposée | ✅ |
| Connexion effective auditée | ✅ |
| Diagnostiquer une ressource indisponible sans aller en base | ✅ |

---

## Éventuelles suites post-v1 (non planifiées, à décider)

Ces items sont explicitement hors-scope v1 dans `CLAUDE.md` et le build plan. Ne pas implémenter sans décision explicite :

- **Tests frontend** : les composants React ont des tests unitaires partiels (login, OTP, portal). Les nouveaux composants (TunnelsClient, EnvironmentsClient enrichi, dashboard gateway) n'ont pas de tests unitaires — acceptable pour v1.
- **Auto-refresh health status** : le bouton "Tester" est manuel. Un polling périodique serait utile mais hors v1.
- **Breakdown gateway-stats par environnement** : les stats sont globales. Un filtre `?env_id=` serait utile mais hors v1.
- **Alerting sur seuils** : PagerDuty, webhooks — hors v1.
- **Full provisioning Cloudflare automatique** : le workflow actuel est semi-assisté (sync tunnels → assign → activate). Une automation complète est hors v1.
- **SSO corporate, permissions fines par ressource, microservices** — hors v1 explicitement.
</work_remaining>

<attempted_approaches>
## Exécution parallèle des 3 plans

**Approche choisie :** dispatch de 3 agents en parallèle dans des worktrees isolés (feature/resource-health-ui, feature/gateway-instrumentation, feature/runbook-exploitation), merge séquentiel après.

**Alternative non retenue :** exécution séquentielle dans la même session via `executing-plans` inline. Rejeté car les plans sont indépendants et le parallélisme est sans risque (worktrees isolés).

**Conflit anticipé et géré :** plans 1 et 2 touchaient tous deux `test_admin_router.py` et `server-admin.ts`. Le conflit sur `server-admin.ts` a été résolu automatiquement par git (ort strategy). Le conflit sur `test_admin_router.py` a nécessité une résolution manuelle (garder les deux blocs de tests).

## Correction bug dans le plan d'instrumentation

Le plan `gateway-instrumentation.md` contenait une incohérence dans le test `test_gateway_stats_counts_events` : le commentaire disait `total_requests == 4` mais la logique (`len(accessed) + upstream_unavailable`) donne 5 (4 accessed + 1 failed). L'instruction à l'agent corrigeait explicitement ce point — l'agent a utilisé `== 5` correctement.
</attempted_approaches>

<critical_context>
## Architecture DevGate

- **Monolithe modulaire** — pas de microservices
- **Backend** : Python FastAPI dans `apps/api/`, venv à `apps/api/.venv/`
- **Frontend** : Next.js dans `apps/web/`
- **DB** : SQLite en test (conftest.py), PostgreSQL en prod
- **Tests** : `cd apps/api && .venv/bin/python -m pytest` (JAMAIS `python -m pytest` — Python système est 3.9.6, venv est 3.11)
- **Gateway** : `apps/api/app/modules/gateway/` — proxy HTTP+WebSocket, vérifie session+grant, injecte CF service tokens
- **Auth** : rate-limiter en mémoire (`RateLimiter`) sur `/auth/start` (5 req/10min) et `/auth/verify` (10 req/5min)
- **Secrets** : `EncryptedDatabaseSecretStore` (AES-256-GCM + HKDF), `DEVGATE_MASTER_KEY` hors base, refs `sec_<uuid>` dans les objets métier

## Modèles de données clés

```python
# Modèles principaux (apps/api/app/shared/models.py)
User, Organization, Project, Environment  # CRUD admin
Session, LoginChallenge                   # Auth
AccessGrant                               # Accès par organisation
AuditEvent                                # Audit append-only
TunnelHealthSnapshot                      # Santé upstream
EncryptedSecret                           # Secret store
DiscoveredTunnel                          # Tunnels CF découverts
ProvisioningJob                           # Saga provisioning CF
```

## Endpoints admin importants

```
GET  /admin/stats                         # Compteurs globaux
GET  /admin/environments                  # Liste avec health_status (NOUVEAU)
POST /admin/environments/{id}/ping        # Ping immédiat upstream
GET  /admin/gateway-stats                 # Stats 24h gateway (NOUVEAU)
POST /admin/sync-tunnels                  # Sync tunnels CF
GET  /admin/discovered-tunnels            # Liste tunnels découverts
POST /admin/discovered-tunnels/{id}/assign # Assigner tunnel à env
POST /admin/environments/{id}/activate    # Lancer saga provisioning
PUT  /admin/environments/{id}/service-token # Stocker service token CF
```

## Saga Provisioning (ADR-001)

États : `pending → creating_access_app → access_app_created → creating_policy → policy_created → service_token_created_unsealed → secret_persisted → creating_dns → active`

5 règles : R1 persister après chaque call CF, R2 DNS seulement si secret_persisted=True, R3 service token = checkpoint critique, R4 pas de retry aveugle, R5 compensation en ordre inverse.

## Conventions de commit

Commits suivent Conventional Commits : `feat(module):`, `fix(module):`, `docs:`, `test(module):`.

## Frontend admin — pages existantes

```
/admin                    → dashboard (stats + gateway stats + activité récente)
/admin/clients            → CRUD organisations
/admin/environments       → CRUD envs + colonne Santé (NOUVEAU)
/admin/access             → grants
/admin/audit              → audit events
/admin/tunnels            → sync + assign + activate CF tunnels
```

## Structure des fichiers API admin

```
apps/web/src/lib/api/
  server-admin.ts   # Server Components — cookie forwarding, types TypeScript
  client.ts         # Client Components — adminApi avec méthodes fetch
```

## Worktrees

Le dossier `.worktrees/` est gitignored. La convention de branch est `feature/<nom-du-plan>`.
</critical_context>

<current_state>
## État final — v1 livrée

**Branche active :** `main`
**Tests :** 125 passants, 0 échecs
**Worktrees actifs :** aucun (tous nettoyés)
**Branches feature :** aucune (toutes mergées et supprimées)

## Fichiers créés dans cette session

| Fichier | Statut |
|---|---|
| `docs/superpowers/plans/2026-04-21-resource-health-ui.md` | Commité, mergé |
| `docs/superpowers/plans/2026-04-21-gateway-instrumentation.md` | Commité, mergé |
| `docs/superpowers/plans/2026-04-21-runbook-exploitation.md` | Commité, mergé |
| `docs/runbook-exploitation.md` | Commité, mergé |

## Fichiers modifiés dans cette session

| Fichier | Modification |
|---|---|
| `apps/api/app/modules/admin/router.py` | `list_environments()` avec health_status + `get_gateway_stats()` |
| `apps/api/app/modules/gateway/service.py` | `proxy_request()` avec timing + audit enrichi |
| `apps/api/tests/integration/test_admin_router.py` | +4 tests (health_status + gateway-stats) |
| `apps/api/tests/integration/test_gateway.py` | +4 tests (latency, is_5xx, is_cf_refused, failed event) |
| `apps/web/src/lib/api/server-admin.ts` | `AdminEnvItem` enrichi + `GatewayStats` + `gatewayStats()` |
| `apps/web/src/lib/api/client.ts` | `adminApi.environments.ping()` |
| `apps/web/src/app/(admin)/admin/environments/EnvironmentsClient.tsx` | Colonne Santé + bouton Tester |
| `apps/web/src/app/(admin)/admin/page.tsx` | Widget gateway stats |
| `docs/planning/build-plan.md` | Statut → `v1 livrée — 2026-04-21` |

## Prochaine action suggérée

Aucune — la v1 est complète. Si une v2 est envisagée, les items post-v1 listés dans `work_remaining` sont les candidats naturels. Consulter `CLAUDE.md` pour les règles d'architecture avant tout nouveau développement.
</current_state>
