"""
Module auth — magic link + OTP
Règles :
- challenge à durée courte (15 min)
- consommable une seule fois
- session cookie HttpOnly Secure SameSite=Lax
- tous les flux critiques produisent des AuditEvents
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session as DbSession

from app.modules.audit.service import audit
from app.shared.exceptions import (
    ChallengeAlreadyUsedException,
    ChallengeExpiredException,
    NotFoundException,
)
from app.shared.models import LoginChallenge, Session, User


OTP_EXPIRY_MINUTES = 10
MAGIC_LINK_EXPIRY_MINUTES = 15
SESSION_TTL_DAYS = 7


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def start_login(email: str, db: DbSession) -> dict:
    """Démarre un login : crée un challenge et envoie l'email."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        # Réponse identique pour éviter l'énumération d'emails
        audit(db, event_type="login.start.unknown_email", metadata={"email": email})
        return {"ok": True, "method": "magic_link"}

    token = secrets.token_urlsafe(32)
    challenge = LoginChallenge(
        user_id=user.id,
        type="magic_link",
        hashed_token=_hash_token(token),
        expires_at=datetime.now(tz=timezone.utc) + timedelta(minutes=MAGIC_LINK_EXPIRY_MINUTES),
    )
    db.add(challenge)
    db.commit()

    audit(db, actor_user_id=user.id, event_type="login.magic_link.requested",
          target_type="login_challenge", target_id=challenge.id)

    # TODO: envoyer l'email via le provider configuré
    # email_provider.send_magic_link(user.email, token, challenge.id)

    return {"ok": True, "method": "magic_link"}


def verify_token(token: str, db: DbSession) -> Session:
    """Valide un token (magic link ou OTP) et crée une session."""
    hashed = _hash_token(token)
    challenge = (
        db.query(LoginChallenge)
        .filter(LoginChallenge.hashed_token == hashed)
        .first()
    )
    if not challenge:
        raise NotFoundException("Token invalide")

    now = datetime.now(tz=timezone.utc)
    if challenge.expires_at.replace(tzinfo=timezone.utc) < now:
        raise ChallengeExpiredException()
    if challenge.used_at is not None:
        raise ChallengeAlreadyUsedException()

    # Consommation
    challenge.used_at = now
    challenge.attempt_count += 1

    session = Session(
        user_id=challenge.user_id,
        expires_at=now + timedelta(days=SESSION_TTL_DAYS),
    )
    db.add(session)

    user = db.query(User).filter(User.id == challenge.user_id).first()
    if user:
        user.last_login_at = now

    db.commit()

    audit(db, actor_user_id=challenge.user_id, event_type="login.session.created",
          target_type="session", target_id=session.id)

    return session
