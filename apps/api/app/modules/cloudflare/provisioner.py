"""
Provisioner saga Cloudflare — ADR-001.

Règles implémentées :
- R1 : persist après chaque appel CF (flush + commit = checkpoint)
- R2 : DNS uniquement si secret_persisted = True
- R3 : service token = checkpoint critique (create-and-seal)
- R4 : pas de retry aveugle si secret non scellé
- R5 : compensation explicite dans l'ordre inverse
"""
import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DbSession

from app.modules.cloudflare.client import CFClient
from app.modules.secrets.store import SecretStore
from app.shared.models import Environment, ProvisioningJob

logger = logging.getLogger(__name__)


class ProvisioningError(Exception):
    """Erreur de provisioning — job passé en failed_recoverable."""


def _persist(job: ProvisioningJob, state: str, db: DbSession, **fields) -> None:
    """Checkpoint : persiste l'état et les IDs CF après chaque appel distant."""
    job.state = state
    job.updated_at = datetime.now(tz=timezone.utc)
    for key, value in fields.items():
        setattr(job, key, value)
    db.flush()


def run_provisioning_job(
    job: ProvisioningJob,
    env: Environment,
    cf,
    secret_store: SecretStore,
    db: DbSession,
) -> str:
    """
    Avance le provisioning jusqu'à 'active' ou état d'erreur.

    Chaque transition persiste immédiatement — un redémarrage peut reprendre
    depuis le dernier checkpoint.

    Retourne le state final.
    """
    try:
        # ── Étape 1 : Access app ───────────────────────────────────
        if job.state == "pending":
            _persist(job, "creating_access_app", db)
            app = cf.create_access_app(
                name=f"devgate-{env.slug}",
                domain=env.public_hostname,
            )
            _persist(job, "access_app_created", db, cloudflare_access_app_id=app.id)
            db.commit()
            logger.info("Job %s: Access app créée (%s)", job.id, app.id)

        # ── Étape 2 : Policy ───────────────────────────────────────
        if job.state == "access_app_created":
            _persist(job, "creating_policy", db)
            policy_id = cf.create_policy(
                app_id=job.cloudflare_access_app_id,
                name=f"allow-devgate-{env.slug}",
            )
            _persist(job, "policy_created", db, cloudflare_policy_id=policy_id)
            db.commit()
            logger.info("Job %s: Policy créée (%s)", job.id, policy_id)

        # ── Étape 3 : Service token (checkpoint critique ADR-001 R3) ──
        if job.state == "policy_created":
            _persist(job, "creating_service_token", db)
            token = cf.create_service_token(name=f"devgate-{env.slug}")

            # Persister l'ID du token avant de tenter de sceller le secret
            _persist(
                job, "service_token_created_unsealed", db,
                cloudflare_service_token_id=token.id,
            )
            db.commit()
            logger.info(
                "Job %s: Service token créé (%s) — scellement du secret...",
                job.id, token.id,
            )

            # Scellement immédiat — si cette étape échoue, le job passe en
            # failed_recoverable et le token doit être révoqué (ADR-001 R4)
            payload = json.dumps({
                "client_id": token.client_id,
                "client_secret": token.client_secret,
            })
            ref = secret_store.put(
                secret_type="cloudflare_service_token",
                plaintext=payload,
                owner_type="environment",
                owner_id=env.id,
            )
            env.service_token_ref = ref
            _persist(job, "secret_persisted", db, secret_persisted=True)
            db.commit()
            logger.info("Job %s: Secret scellé (ref=%s)", job.id, ref)

        # ── Étape 4 : DNS (dernier, ADR-001 R2) ────────────────────
        if job.state == "secret_persisted":
            # Garantie explicite : ne jamais publier le DNS sans secret scellé
            if not job.secret_persisted:
                raise ProvisioningError(
                    "Tentative de publication DNS sans secret scellé — bloqué par ADR-001 R2"
                )

            tunnel_id = env.cloudflare_tunnel_id
            if not tunnel_id:
                raise ProvisioningError(
                    "cloudflare_tunnel_id absent sur l'environnement — assignez un tunnel d'abord"
                )

            _persist(job, "creating_dns", db)
            dns_record_id = cf.create_dns_cname(
                name=env.public_hostname,
                tunnel_id=tunnel_id,
            )
            _persist(job, "active", db, dns_record_id=dns_record_id, dns_published=True)
            env.status = "active"
            db.commit()
            logger.info("Job %s: DNS publié — environnement actif", job.id)

        return job.state

    except ProvisioningError as e:
        # Erreur métier explicite
        import traceback
        job.state = "failed_recoverable"
        job.updated_at = datetime.now(tz=timezone.utc)
        logger.error("Provisioning error job %s: %s", job.id, traceback.format_exc(limit=3))
        job.last_error = str(e)
        db.commit()
        raise
    except Exception as e:
        # Erreur CF API ou autre
        logger.error("Job %s: erreur inattendue à l'état %s", job.id, job.state, exc_info=True)
        job.state = "failed_recoverable"
        job.last_error = str(e)
        job.updated_at = datetime.now(tz=timezone.utc)
        db.commit()
        raise ProvisioningError(str(e)) from e


def compensate_provisioning_job(
    job: ProvisioningJob,
    cf,
    db: DbSession,
) -> str:
    """
    Compensation ADR-001 R5 — suppression dans l'ordre inverse.
    DNS → service token → policy → Access app.

    Retourne 'rolled_back' si succès complet, 'compensating' si erreurs partielles.
    """
    job.state = "compensating"
    job.updated_at = datetime.now(tz=timezone.utc)
    db.commit()

    errors: list[str] = []

    if job.dns_record_id:
        try:
            cf.delete_dns_record(job.dns_record_id)
            job.dns_record_id = None
            job.dns_published = False
            db.flush()
        except Exception as e:
            errors.append(f"dns: {e}")
            logger.warning(
                "Compensation: échec suppression DNS %s: %s", job.dns_record_id, e
            )

    if job.cloudflare_service_token_id:
        try:
            cf.revoke_service_token(job.cloudflare_service_token_id)
        except Exception as e:
            errors.append(f"service_token: {e}")
            logger.warning(
                "Compensation: échec révocation token %s: %s",
                job.cloudflare_service_token_id, e,
            )

    if job.cloudflare_policy_id and job.cloudflare_access_app_id:
        try:
            cf.delete_policy(job.cloudflare_access_app_id, job.cloudflare_policy_id)
        except Exception as e:
            errors.append(f"policy: {e}")
            logger.warning(
                "Compensation: échec suppression policy %s: %s",
                job.cloudflare_policy_id, e,
            )

    if job.cloudflare_access_app_id:
        try:
            cf.delete_access_app(job.cloudflare_access_app_id)
        except Exception as e:
            errors.append(f"access_app: {e}")
            logger.warning(
                "Compensation: échec suppression app %s: %s",
                job.cloudflare_access_app_id, e,
            )

    if errors:
        job.last_error = "; ".join(errors)
        # Reste en "compensating" — intervention manuelle requise
        logger.error(
            "Compensation partielle pour job %s: %s", job.id, job.last_error
        )
    else:
        job.state = "rolled_back"
        logger.info("Job %s: compensation complète → rolled_back", job.id)

    job.updated_at = datetime.now(tz=timezone.utc)
    db.commit()
    return job.state
