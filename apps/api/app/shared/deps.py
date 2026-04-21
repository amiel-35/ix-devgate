"""Dépendances FastAPI partagées — session, DB, rôles."""
from datetime import datetime, timezone

from fastapi import Cookie, Depends
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.shared.exceptions import ForbiddenException, UnauthorizedException
from app.shared.models import Session, User


def get_current_session(
    devgate_session: str | None = Cookie(default=None),
    db: DbSession = Depends(get_db),
) -> Session:
    if not devgate_session:
        raise UnauthorizedException()

    session = db.query(Session).filter(Session.id == devgate_session).first()
    if not session:
        raise UnauthorizedException()

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(tz=timezone.utc):
        raise UnauthorizedException()

    user = db.query(User).filter(User.id == session.user_id).first()
    if not user or user.status != "active":
        raise UnauthorizedException("Compte désactivé")

    session.last_seen_at = datetime.now(tz=timezone.utc)
    db.commit()
    return session


def get_current_user(
    session: Session = Depends(get_current_session),
    db: DbSession = Depends(get_db),
) -> User:
    user = db.query(User).filter(User.id == session.user_id).first()
    if not user:
        raise UnauthorizedException()
    if user.status != "active":
        raise UnauthorizedException("Compte désactivé")
    return user


def require_agency_admin(user: User = Depends(get_current_user)) -> User:
    """Exige un grant agency_admin actif. Le champ `kind` n'est pas suffisant."""
    has_admin_grant = any(
        g.role == "agency_admin" and g.revoked_at is None
        for g in user.grants
    )
    if not has_admin_grant:
        raise ForbiddenException("Réservé aux administrateurs agence")
    return user
