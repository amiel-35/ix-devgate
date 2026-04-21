from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.database import get_db
from app.modules.auth import rate_limit as _rate_limit_mod
from app.modules.auth.schemas import (
    LoginStartRequest, LoginStartResponse,
    LoginVerifyRequest, LoginVerifyResponse,
)
from app.modules.auth.service import start_login, verify_token
from app.shared.deps import get_current_session

router = APIRouter()

SESSION_COOKIE = "devgate_session"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 7


@router.post("/start", response_model=LoginStartResponse)
def login_start(
    body: LoginStartRequest,
    request: Request,
    db: DbSession = Depends(get_db),
):
    normalized_email = body.email.strip().lower()
    key = f"{request.client.host if request.client else 'unknown'}|{normalized_email}"
    _rate_limit_mod.login_start_limiter.check(key)
    return start_login(body.email, db, method=body.method)


@router.post("/verify", response_model=LoginVerifyResponse)
def login_verify(body: LoginVerifyRequest, request: Request, response: Response, db: DbSession = Depends(get_db)):
    key = request.client.host if request.client else "unknown"
    _rate_limit_mod.login_verify_limiter.check(key)
    session = verify_token(body.token, db)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session.id,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=SESSION_TTL_SECONDS,
    )
    return LoginVerifyResponse(ok=True, session_created=True, redirect_to="/portal")


@router.post("/logout")
def logout(
    response: Response,
    current_session=Depends(get_current_session),
    db: DbSession = Depends(get_db),
):
    db.delete(current_session)
    db.commit()
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        httponly=True,
    )
    return {"ok": True}
