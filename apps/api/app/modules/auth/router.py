from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.modules.auth.schemas import (
    LoginStartRequest, LoginStartResponse,
    LoginVerifyRequest, LoginVerifyResponse,
)
from app.modules.auth.service import start_login, verify_token
from app.shared.deps import get_current_session

router = APIRouter()

SESSION_COOKIE = "devgate_session"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 jours


@router.post("/start", response_model=LoginStartResponse)
def login_start(body: LoginStartRequest, db: DbSession = Depends(get_db)):
    # Rate limiting : TODO ajouter slowapi ou middleware dédié
    result = start_login(body.email, db)
    return result


@router.post("/verify", response_model=LoginVerifyResponse)
def login_verify(body: LoginVerifyRequest, response: Response, db: DbSession = Depends(get_db)):
    session = verify_token(body.token, db)

    response.set_cookie(
        key=SESSION_COOKIE,
        value=session.id,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=SESSION_TTL_SECONDS,
    )
    return LoginVerifyResponse(ok=True, session_created=True, redirect_to="/portal")


@router.post("/logout")
def logout(response: Response, current_session=Depends(get_current_session)):
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}
