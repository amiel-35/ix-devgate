from datetime import datetime, timedelta, timezone

from fastapi import Depends

from app.shared.deps import get_current_user
from app.shared.models import Session as SessionModel, User


def _setup_user_and_session(db_session, user_id="u1", session_id="s1", expires_in_days=1):
    user = User(id=user_id, email=f"{user_id}@example.com", display_name="T",
                kind="client", status="active")
    session = SessionModel(
        id=session_id,
        user_id=user_id,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=expires_in_days),
    )
    db_session.add_all([user, session])
    db_session.commit()
    return user, session


def test_no_cookie_returns_401(client):
    @client.app.get("/_test/me_nocookie")
    def _me(user=Depends(get_current_user)):
        return {"id": user.id}

    res = client.get("/_test/me_nocookie")
    assert res.status_code == 401


def test_valid_session_returns_user(client, db_session):
    _setup_user_and_session(db_session, user_id="u1", session_id="s-valid")

    @client.app.get("/_test/me_valid")
    def _me(u=Depends(get_current_user)):
        return {"id": u.id}

    client.cookies.set("devgate_session", "s-valid")
    res = client.get("/_test/me_valid")
    assert res.status_code == 200
    assert res.json() == {"id": "u1"}


def test_unknown_session_id_returns_401(client):
    @client.app.get("/_test/me_unknown")
    def _me(u=Depends(get_current_user)):
        return {"id": u.id}

    client.cookies.set("devgate_session", "does-not-exist")
    res = client.get("/_test/me_unknown")
    assert res.status_code == 401


def test_expired_session_returns_401(client, db_session):
    user = User(id="u-exp", email="e@x.com", display_name="E", kind="client", status="active")
    session = SessionModel(
        id="s-exp",
        user_id="u-exp",
        expires_at=datetime.now(tz=timezone.utc) - timedelta(minutes=1),
    )
    db_session.add_all([user, session])
    db_session.commit()

    @client.app.get("/_test/me_expired")
    def _me(u=Depends(get_current_user)):
        return {"id": u.id}

    client.cookies.set("devgate_session", "s-exp")
    res = client.get("/_test/me_expired")
    assert res.status_code == 401
