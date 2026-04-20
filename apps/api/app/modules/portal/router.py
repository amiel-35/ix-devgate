from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.modules.portal.schemas import EnvironmentListItem, MeResponse, SessionItem
from app.modules.portal.service import get_environments_for_user
from app.shared.deps import get_current_session, get_current_user
from app.shared.models import Session as SessionModel, User

router = APIRouter()


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)):
    return MeResponse(id=user.id, email=user.email, display_name=user.display_name)


@router.get("/me/environments", response_model=list[EnvironmentListItem])
def my_environments(user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    return get_environments_for_user(user, db)


@router.get("/me/sessions", response_model=list[SessionItem])
def my_sessions(
    current_session: SessionModel = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    sessions = db.query(SessionModel).filter(SessionModel.user_id == user.id).all()
    return [
        SessionItem(
            id=s.id,
            expires_at=s.expires_at.isoformat(),
            last_seen_at=s.last_seen_at.isoformat(),
            ip=s.ip,
            user_agent=s.user_agent,
            is_current=(s.id == current_session.id),
        )
        for s in sessions
    ]


@router.delete("/me/sessions/{session_id}", status_code=204)
def revoke_session(
    session_id: str,
    current_session: SessionModel = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    session = db.query(SessionModel).filter(
        SessionModel.id == session_id,
        SessionModel.user_id == user.id,
    ).first()
    if session and session.id != current_session.id:
        db.delete(session)
        db.commit()
