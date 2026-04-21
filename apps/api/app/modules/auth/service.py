"""
Module auth — magic link + OTP
Règles :
- challenge à durée courte (15 min pour magic link, 10 min pour OTP)
- consommable une seule fois
- session cookie HttpOnly Secure SameSite=Lax
- tous les flux critiques produisent des AuditEvents
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.modules.audit.service import audit
from app.modules.email import get_email_provider
from app.shared.exceptions import (
    ChallengeAlreadyUsedException,
    ChallengeExpiredException,
    ForbiddenException,
    NotFoundException,
)
from app.shared.models import LoginChallenge, Session, User


OTP_EXPIRY_MINUTES = 10
MAGIC_LINK_EXPIRY_MINUTES = 15
SESSION_TTL_DAYS = 7
MAX_CHALLENGE_ATTEMPTS = 5


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def start_login(email: str, db: DbSession, method: str = "magic_link") -> dict:
    """Démarre un login : crée un challenge et envoie l'email.

    Anti-enumeration : un email inconnu renvoie la même réponse qu'un connu,
    mais sans créer de challenge ni envoyer d'email.
    """
    user = db.query(User).filter(User.email == email).first()
    if not user:
        audit(db, event_type="login.start.unknown_email", metadata={"email": email})
        db.commit()
        return {"ok": True, "method": method}

    provider = get_email_provider()

    if method == "otp":
        code = _generate_otp()
        challenge = LoginChallenge(
            user_id=user.id,
            type="otp",
            hashed_token=_hash_token(code),
            expires_at=datetime.now(tz=timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES),
        )
        db.add(challenge)
        db.flush()
        audit(db, actor_user_id=user.id, event_type="login.otp.requested",
              target_type="login_challenge", target_id=challenge.id)
        db.commit()
        provider.send_otp(to=user.email, code=code)
        return {"ok": True, "method": "otp"}

    # magic_link (default)
    token = secrets.token_urlsafe(32)
    challenge = LoginChallenge(
        user_id=user.id,
        type="magic_link",
        hashed_token=_hash_token(token),
        expires_at=datetime.now(tz=timezone.utc) + timedelta(minutes=MAGIC_LINK_EXPIRY_MINUTES),
    )
    db.add(challenge)
    db.flush()
    audit(db, actor_user_id=user.id, event_type="login.magic_link.requested",
          target_type="login_challenge", target_id=challenge.id)
    db.commit()

    link = f"{settings.FRONTEND_BASE_URL}/verify?token={token}"
    provider.send_magic_link(to=user.email, link=link)
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

    if challenge.attempt_count >= MAX_CHALLENGE_ATTEMPTS:
        raise ForbiddenException("Challenge verrouillé après trop de tentatives")

    now = datetime.now(tz=timezone.utc)
    if challenge.expires_at.replace(tzinfo=timezone.utc) < now:
        challenge.attempt_count += 1
        db.commit()
        raise ChallengeExpiredException()
    if challenge.used_at is not None:
        challenge.attempt_count += 1
        db.commit()
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
