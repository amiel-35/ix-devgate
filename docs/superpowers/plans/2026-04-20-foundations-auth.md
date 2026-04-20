# Fondations + Auth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Livrer une base DevGate exécutable en local où un utilisateur connu se connecte via magic link ou OTP et voit une session persistée — Phases 1 + 2 du build-plan.

**Architecture:** Monolithe modulaire FastAPI + Next.js sur PostgreSQL. Le backend porte la source de vérité (users, challenges, sessions, audit). Le frontend rend les écrans E01–E03 + E09–E11 et ne contient aucune logique Cloudflare ni de session côté client. Session = cookie `HttpOnly Secure SameSite=Lax` géré par FastAPI.

**Tech Stack:** FastAPI 0.115 · SQLAlchemy 2.0 · Alembic · PostgreSQL 16 · pytest · Next.js 15 · React 19 · TypeScript 5 · Vitest + Testing Library · Resend (email).

**Source de vérité visuelle :** `docs/ds/mockups/devgate-e0{1,2,3,9}-*.mockup.html`, `devgate-e1{0,1}-*.mockup.html`.

---

## File Structure

### Backend (`apps/api/`)

| Fichier | Responsabilité |
|---------|----------------|
| `app/modules/email/provider.py` | **Create** — Interface `EmailProvider` + `FakeEmailProvider` (tests) + `ResendEmailProvider` (prod) |
| `app/modules/email/__init__.py` | **Create** — export + factory `get_email_provider()` |
| `app/modules/auth/service.py` | **Modify** — `start_login()`, `verify_token()`, helpers hash/token (déjà scaffolded, à compléter) |
| `app/modules/auth/router.py` | **Modify** — `POST /auth/start`, `POST /auth/verify`, `POST /auth/logout` |
| `app/modules/auth/schemas.py` | **Modify** — Pydantic schemas déjà scaffolded, ajouter `OtpVerifyRequest` |
| `app/modules/auth/rate_limit.py` | **Create** — rate limiter simple en mémoire pour `/auth/start` |
| `app/modules/audit/service.py` | **Modify** — déjà scaffolded, vérifier signature |
| `app/shared/deps.py` | **Modify** — `get_current_session`, `get_current_user` déjà scaffolded, ajouter tests |
| `app/shared/models.py` | **Keep** — modèles déjà scaffolded |
| `app/migrations/versions/0001_initial.py` | **Create** — migration initiale tous modèles |
| `app/seeds.py` | **Create** — seed minimal pour dev (1 agence admin, 1 client, 1 env) |
| `tests/conftest.py` | **Create** — fixtures DB SQLite in-memory + TestClient |
| `tests/unit/test_auth_service.py` | **Create** — tests unitaires service auth |
| `tests/unit/test_audit.py` | **Modify** — tests déjà scaffolded, compléter |
| `tests/unit/test_email_provider.py` | **Create** — tests email provider |
| `tests/unit/test_rate_limit.py` | **Create** — tests rate limit |
| `tests/integration/test_auth_router.py` | **Create** — tests end-to-end routeur |
| `tests/integration/test_session_deps.py` | **Create** — tests `get_current_session` |

### Frontend (`apps/web/`)

| Fichier | Responsabilité |
|---------|----------------|
| `src/app/(auth)/layout.tsx` | **Create** — layout standalone (bg atmosphérique, card centrée) |
| `src/app/(auth)/login/page.tsx` | **Modify** — E01 complet avec UI mockup |
| `src/app/(auth)/magic-sent/MagicSentContent.tsx` | **Modify** — E02 complet |
| `src/app/(auth)/otp/OtpContent.tsx` | **Modify** — E03 complet (6 inputs, timer) |
| `src/app/(auth)/link-expired/page.tsx` | **Modify** — E09 complet |
| `src/app/session-expired/page.tsx` | **Modify** — E10 complet |
| `src/app/access-denied/page.tsx` | **Modify** — E11 complet |
| `src/components/auth/AuthCard.tsx` | **Create** — card partagée (logo agence, layout) |
| `src/components/auth/OtpInput.tsx` | **Create** — input OTP 6 chiffres avec focus auto |
| `src/components/auth/StateCard.tsx` | **Create** — card d'état (icône + titre + actions) |
| `src/components/shared/Button.tsx` | **Create** — Primary / Secondary / Link variants |
| `src/app/globals.css` | **Modify** — tokens design system complets depuis mockup |
| `src/lib/api/client.ts` | **Modify** — compléter `authApi` (déjà scaffolded) |
| `src/test/setup.ts` | **Create** — setup Vitest + Testing Library |
| `vitest.config.ts` | **Create** — config Vitest |
| `src/app/(auth)/login/__tests__/LoginPage.test.tsx` | **Create** — tests composant |
| `src/app/(auth)/otp/__tests__/OtpContent.test.tsx` | **Create** — tests composant |
| `src/components/auth/__tests__/OtpInput.test.tsx` | **Create** — tests composant |

---

## Task 1: Backend — fixtures pytest + DB de test

**Files:**
- Create: `apps/api/tests/conftest.py`

- [ ] **Step 1.1: Créer `conftest.py` avec fixtures DB SQLite in-memory**

```python
# apps/api/tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()
```

- [ ] **Step 1.2: Vérifier que pytest découvre les fixtures**

Run: `cd apps/api && pytest tests/ --collect-only 2>&1 | head -30`
Expected: les fichiers tests existants sont collectés sans erreur d'import.

- [ ] **Step 1.3: Commit**

```bash
git add apps/api/tests/conftest.py
git commit -m "test(api): add pytest fixtures for in-memory DB and TestClient"
```

---

## Task 2: Backend — audit service (TDD)

**Files:**
- Modify: `apps/api/app/modules/audit/service.py`
- Modify: `apps/api/tests/unit/test_audit.py`

- [ ] **Step 2.1: Écrire les tests pour `audit()`**

```python
# apps/api/tests/unit/test_audit.py
from app.modules.audit.service import audit
from app.shared.models import AuditEvent


def test_audit_creates_event_with_all_fields(db_session):
    event = audit(
        db_session,
        event_type="login.session.created",
        actor_user_id="u1",
        target_type="session",
        target_id="s1",
        metadata={"ip": "1.2.3.4"},
    )
    db_session.commit()

    saved = db_session.query(AuditEvent).filter(AuditEvent.id == event.id).first()
    assert saved is not None
    assert saved.event_type == "login.session.created"
    assert saved.actor_user_id == "u1"
    assert saved.target_type == "session"
    assert saved.target_id == "s1"
    assert saved.metadata_json == {"ip": "1.2.3.4"}


def test_audit_minimal_fields(db_session):
    event = audit(db_session, event_type="admin.organization.created")
    db_session.commit()
    saved = db_session.query(AuditEvent).filter(AuditEvent.id == event.id).first()
    assert saved.event_type == "admin.organization.created"
    assert saved.actor_user_id is None
    assert saved.metadata_json is None
```

- [ ] **Step 2.2: Lancer les tests, vérifier qu'ils passent**

Run: `cd apps/api && pytest tests/unit/test_audit.py -v`
Expected: 2 PASSED.

Si échec : vérifier que `audit()` fait bien `db.flush()` (déjà dans le scaffold).

- [ ] **Step 2.3: Commit**

```bash
git add apps/api/tests/unit/test_audit.py
git commit -m "test(api): cover audit service with in-memory DB"
```

---

## Task 3: Backend — EmailProvider interface + FakeEmailProvider (TDD)

**Files:**
- Create: `apps/api/app/modules/email/__init__.py`
- Create: `apps/api/app/modules/email/provider.py`
- Create: `apps/api/tests/unit/test_email_provider.py`

- [ ] **Step 3.1: Écrire le test FakeEmailProvider d'abord**

```python
# apps/api/tests/unit/test_email_provider.py
from app.modules.email.provider import FakeEmailProvider


def test_fake_provider_records_magic_link():
    provider = FakeEmailProvider()
    provider.send_magic_link(
        to="user@example.com",
        link="https://devgate.test/verify?token=abc",
    )
    assert len(provider.sent) == 1
    assert provider.sent[0]["to"] == "user@example.com"
    assert provider.sent[0]["kind"] == "magic_link"
    assert "abc" in provider.sent[0]["link"]


def test_fake_provider_records_otp():
    provider = FakeEmailProvider()
    provider.send_otp(to="user@example.com", code="371829")
    assert provider.sent[-1]["kind"] == "otp"
    assert provider.sent[-1]["code"] == "371829"


def test_fake_provider_clear():
    provider = FakeEmailProvider()
    provider.send_otp(to="a@b.com", code="111111")
    provider.clear()
    assert provider.sent == []
```

- [ ] **Step 3.2: Run — doit échouer avec ImportError**

Run: `cd apps/api && pytest tests/unit/test_email_provider.py -v`
Expected: `ModuleNotFoundError: No module named 'app.modules.email.provider'`.

- [ ] **Step 3.3: Créer l'interface et FakeEmailProvider**

```python
# apps/api/app/modules/email/provider.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class EmailProvider(ABC):
    @abstractmethod
    def send_magic_link(self, to: str, link: str) -> None: ...

    @abstractmethod
    def send_otp(self, to: str, code: str) -> None: ...


class FakeEmailProvider(EmailProvider):
    """Capture les envois en mémoire. Utilisé en tests et dev."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def send_magic_link(self, to: str, link: str) -> None:
        self.sent.append({"kind": "magic_link", "to": to, "link": link})

    def send_otp(self, to: str, code: str) -> None:
        self.sent.append({"kind": "otp", "to": to, "code": code})

    def clear(self) -> None:
        self.sent = []
```

```python
# apps/api/app/modules/email/__init__.py
from app.config import settings
from app.modules.email.provider import EmailProvider, FakeEmailProvider

_default_provider: EmailProvider | None = None


def get_email_provider() -> EmailProvider:
    """Factory — FakeEmailProvider en dev/test, Resend en prod.
    Le provider réel (Resend) sera ajouté dans une tâche ultérieure.
    """
    global _default_provider
    if _default_provider is None:
        _default_provider = FakeEmailProvider()
    return _default_provider


def override_email_provider(provider: EmailProvider) -> None:
    """Pour les tests."""
    global _default_provider
    _default_provider = provider
```

- [ ] **Step 3.4: Run — doit passer**

Run: `cd apps/api && pytest tests/unit/test_email_provider.py -v`
Expected: 3 PASSED.

- [ ] **Step 3.5: Commit**

```bash
git add apps/api/app/modules/email/ apps/api/tests/unit/test_email_provider.py
git commit -m "feat(api): add EmailProvider interface and FakeEmailProvider"
```

---

## Task 4: Backend — login challenge creation (TDD)

**Files:**
- Modify: `apps/api/app/modules/auth/service.py`
- Create: `apps/api/tests/unit/test_auth_service.py`

- [ ] **Step 4.1: Écrire les tests pour `start_login()`**

```python
# apps/api/tests/unit/test_auth_service.py
from datetime import datetime, timezone

from app.modules.auth.service import start_login, verify_token
from app.modules.email import get_email_provider, override_email_provider
from app.modules.email.provider import FakeEmailProvider
from app.shared.models import AuditEvent, LoginChallenge, User


def _make_user(db_session, email="user@example.com", kind="client"):
    user = User(email=email, display_name="Test", kind=kind, status="active")
    db_session.add(user)
    db_session.commit()
    return user


def test_start_login_known_email_creates_challenge(db_session):
    fake = FakeEmailProvider()
    override_email_provider(fake)
    user = _make_user(db_session)

    result = start_login("user@example.com", db_session)

    assert result == {"ok": True, "method": "magic_link"}
    challenges = db_session.query(LoginChallenge).filter(LoginChallenge.user_id == user.id).all()
    assert len(challenges) == 1
    assert challenges[0].type == "magic_link"
    assert challenges[0].used_at is None
    assert challenges[0].expires_at > datetime.now(tz=timezone.utc)

    assert len(fake.sent) == 1
    assert fake.sent[0]["kind"] == "magic_link"
    assert fake.sent[0]["to"] == "user@example.com"


def test_start_login_unknown_email_returns_ok_but_no_challenge(db_session):
    """Anti-enumeration : la réponse est identique."""
    fake = FakeEmailProvider()
    override_email_provider(fake)

    result = start_login("unknown@example.com", db_session)

    assert result == {"ok": True, "method": "magic_link"}
    assert db_session.query(LoginChallenge).count() == 0
    assert fake.sent == []
    # L'événement audit doit quand même être créé
    events = db_session.query(AuditEvent).filter(
        AuditEvent.event_type == "login.start.unknown_email"
    ).all()
    assert len(events) == 1


def test_start_login_audits_request(db_session):
    override_email_provider(FakeEmailProvider())
    user = _make_user(db_session)

    start_login(user.email, db_session)

    events = db_session.query(AuditEvent).filter(
        AuditEvent.event_type == "login.magic_link.requested",
        AuditEvent.actor_user_id == user.id,
    ).all()
    assert len(events) == 1
```

- [ ] **Step 4.2: Run — au moins le premier test doit échouer**

Run: `cd apps/api && pytest tests/unit/test_auth_service.py::test_start_login_known_email_creates_challenge -v`
Expected: FAIL (le scaffold actuel n'envoie pas l'email, ne commit pas toujours correctement).

- [ ] **Step 4.3: Compléter `start_login()`**

```python
# apps/api/app/modules/auth/service.py — remplacer la fonction start_login
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session as DbSession

from app.modules.audit.service import audit
from app.modules.email import get_email_provider
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


def _generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def start_login(email: str, db: DbSession, method: str = "magic_link") -> dict:
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

    # magic_link
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

    link = f"http://localhost:3000/verify?token={token}"
    provider.send_magic_link(to=user.email, link=link)
    return {"ok": True, "method": "magic_link"}
```

- [ ] **Step 4.4: Run — tests doivent passer**

Run: `cd apps/api && pytest tests/unit/test_auth_service.py -v -k start_login`
Expected: 3 PASSED.

- [ ] **Step 4.5: Commit**

```bash
git add apps/api/app/modules/auth/service.py apps/api/tests/unit/test_auth_service.py
git commit -m "feat(api): implement start_login with magic link and OTP"
```

---

## Task 5: Backend — login challenge verification (TDD)

**Files:**
- Modify: `apps/api/app/modules/auth/service.py`
- Modify: `apps/api/tests/unit/test_auth_service.py`

- [ ] **Step 5.1: Ajouter les tests de `verify_token`**

```python
# apps/api/tests/unit/test_auth_service.py — ajouter en bas
from datetime import timedelta

import pytest

from app.shared.exceptions import ChallengeAlreadyUsedException, ChallengeExpiredException, NotFoundException


def test_verify_token_creates_session_and_marks_challenge_used(db_session):
    override_email_provider(FakeEmailProvider())
    user = _make_user(db_session)
    start_login(user.email, db_session)
    # Récupérer le token réel depuis le FakeProvider
    provider = get_email_provider()
    link = provider.sent[0]["link"]
    token = link.split("token=")[1]

    session = verify_token(token, db_session)

    assert session.user_id == user.id
    assert session.expires_at > datetime.now(tz=timezone.utc) + timedelta(days=6)

    challenge = db_session.query(LoginChallenge).filter(LoginChallenge.user_id == user.id).first()
    assert challenge.used_at is not None

    db_session.refresh(user)
    assert user.last_login_at is not None


def test_verify_token_invalid_raises_not_found(db_session):
    with pytest.raises(NotFoundException):
        verify_token("no-such-token", db_session)


def test_verify_token_expired_raises(db_session):
    user = _make_user(db_session)
    challenge = LoginChallenge(
        user_id=user.id,
        type="magic_link",
        hashed_token=_hash_token("expired-token"),
        expires_at=datetime.now(tz=timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(challenge)
    db_session.commit()

    with pytest.raises(ChallengeExpiredException):
        verify_token("expired-token", db_session)


def test_verify_token_already_used_raises(db_session):
    user = _make_user(db_session)
    challenge = LoginChallenge(
        user_id=user.id,
        type="magic_link",
        hashed_token=_hash_token("used-token"),
        expires_at=datetime.now(tz=timezone.utc) + timedelta(minutes=10),
        used_at=datetime.now(tz=timezone.utc),
    )
    db_session.add(challenge)
    db_session.commit()

    with pytest.raises(ChallengeAlreadyUsedException):
        verify_token("used-token", db_session)


def test_verify_token_audits_session_creation(db_session):
    override_email_provider(FakeEmailProvider())
    user = _make_user(db_session)
    start_login(user.email, db_session)
    token = get_email_provider().sent[0]["link"].split("token=")[1]

    session = verify_token(token, db_session)

    events = db_session.query(AuditEvent).filter(
        AuditEvent.event_type == "login.session.created",
        AuditEvent.target_id == session.id,
    ).all()
    assert len(events) == 1
```

- [ ] **Step 5.2: Run — tests `verify_token_*` doivent tous échouer ou passer selon le scaffold**

Run: `cd apps/api && pytest tests/unit/test_auth_service.py -v -k verify_token`
Expected: certains FAIL (le scaffold ne gère pas tout).

- [ ] **Step 5.3: S'assurer que `verify_token` dans le service est correct**

Le scaffold est déjà correct pour l'essentiel. Vérifier que ces lignes sont présentes dans `apps/api/app/modules/auth/service.py` :

```python
def verify_token(token: str, db: DbSession) -> Session:
    hashed = _hash_token(token)
    challenge = (
        db.query(LoginChallenge).filter(LoginChallenge.hashed_token == hashed).first()
    )
    if not challenge:
        raise NotFoundException("Token invalide")

    now = datetime.now(tz=timezone.utc)
    expires_at = challenge.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise ChallengeExpiredException()
    if challenge.used_at is not None:
        raise ChallengeAlreadyUsedException()

    challenge.used_at = now
    challenge.attempt_count += 1

    session = Session(
        user_id=challenge.user_id,
        expires_at=now + timedelta(days=SESSION_TTL_DAYS),
    )
    db.add(session)
    db.flush()

    user = db.query(User).filter(User.id == challenge.user_id).first()
    if user:
        user.last_login_at = now

    audit(db, actor_user_id=challenge.user_id, event_type="login.session.created",
          target_type="session", target_id=session.id)
    db.commit()
    return session
```

- [ ] **Step 5.4: Run — tous les tests doivent passer**

Run: `cd apps/api && pytest tests/unit/test_auth_service.py -v`
Expected: 8 PASSED (3 start_login + 5 verify_token).

- [ ] **Step 5.5: Commit**

```bash
git add apps/api/app/modules/auth/service.py apps/api/tests/unit/test_auth_service.py
git commit -m "feat(api): implement verify_token with expiry, reuse and audit checks"
```

---

## Task 6: Backend — rate limiter (TDD)

**Files:**
- Create: `apps/api/app/modules/auth/rate_limit.py`
- Create: `apps/api/tests/unit/test_rate_limit.py`

- [ ] **Step 6.1: Écrire les tests**

```python
# apps/api/tests/unit/test_rate_limit.py
import time

import pytest

from app.modules.auth.rate_limit import RateLimitExceeded, RateLimiter


def test_allows_under_limit():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    limiter.check("user@example.com")
    limiter.check("user@example.com")
    limiter.check("user@example.com")


def test_blocks_over_limit():
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    limiter.check("user@example.com")
    limiter.check("user@example.com")
    with pytest.raises(RateLimitExceeded):
        limiter.check("user@example.com")


def test_window_expires():
    limiter = RateLimiter(max_requests=1, window_seconds=1)
    limiter.check("user@example.com")
    time.sleep(1.1)
    limiter.check("user@example.com")  # ne doit pas lever


def test_keys_are_isolated():
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    limiter.check("a@b.com")
    limiter.check("c@d.com")  # clé différente, ne doit pas lever
```

- [ ] **Step 6.2: Run — doit échouer ImportError**

Run: `cd apps/api && pytest tests/unit/test_rate_limit.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 6.3: Implémenter le rate limiter**

```python
# apps/api/app/modules/auth/rate_limit.py
"""Rate limiter en mémoire — suffisant pour v1 monolithe single-instance.
À remplacer par Redis si scale-out."""
import time
from collections import defaultdict, deque
from fastapi import HTTPException, status


class RateLimitExceeded(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives, réessayez dans quelques minutes",
        )


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        bucket = self._hits[key]
        # purge
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            raise RateLimitExceeded()
        bucket.append(now)


# Instance partagée pour /auth/start — 5 tentatives par 10 minutes
login_start_limiter = RateLimiter(max_requests=5, window_seconds=600)
```

- [ ] **Step 6.4: Run — tests passent**

Run: `cd apps/api && pytest tests/unit/test_rate_limit.py -v`
Expected: 4 PASSED.

- [ ] **Step 6.5: Commit**

```bash
git add apps/api/app/modules/auth/rate_limit.py apps/api/tests/unit/test_rate_limit.py
git commit -m "feat(api): add in-memory rate limiter for auth endpoints"
```

---

## Task 7: Backend — auth router endpoints (TDD)

**Files:**
- Modify: `apps/api/app/modules/auth/router.py`
- Modify: `apps/api/app/modules/auth/schemas.py`
- Create: `apps/api/tests/integration/test_auth_router.py`

- [ ] **Step 7.1: Écrire les tests router**

```python
# apps/api/tests/integration/test_auth_router.py
from datetime import datetime, timezone

from app.modules.email import get_email_provider, override_email_provider
from app.modules.email.provider import FakeEmailProvider
from app.shared.models import LoginChallenge, Session, User


def _make_user(db_session, email="user@example.com"):
    user = User(email=email, display_name="U", kind="client", status="active")
    db_session.add(user)
    db_session.commit()
    return user


def test_start_magic_link_returns_200(client, db_session):
    override_email_provider(FakeEmailProvider())
    _make_user(db_session)

    res = client.post("/auth/start", json={"email": "user@example.com"})

    assert res.status_code == 200
    assert res.json() == {"ok": True, "method": "magic_link"}


def test_start_otp_returns_200(client, db_session):
    override_email_provider(FakeEmailProvider())
    _make_user(db_session)

    res = client.post("/auth/start", json={"email": "user@example.com", "method": "otp"})

    assert res.status_code == 200
    assert res.json() == {"ok": True, "method": "otp"}
    assert get_email_provider().sent[0]["kind"] == "otp"


def test_start_invalid_email_returns_422(client):
    res = client.post("/auth/start", json={"email": "not-an-email"})
    assert res.status_code == 422


def test_verify_valid_token_sets_cookie(client, db_session):
    override_email_provider(FakeEmailProvider())
    _make_user(db_session)
    client.post("/auth/start", json={"email": "user@example.com"})
    token = get_email_provider().sent[0]["link"].split("token=")[1]

    res = client.post("/auth/verify", json={"token": token})

    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["session_created"] is True
    assert body["redirect_to"] == "/portal"
    assert "devgate_session" in res.cookies


def test_verify_invalid_token_returns_404(client):
    res = client.post("/auth/verify", json={"token": "invalid"})
    assert res.status_code == 404


def test_logout_clears_cookie(client, db_session):
    override_email_provider(FakeEmailProvider())
    _make_user(db_session)
    client.post("/auth/start", json={"email": "user@example.com"})
    token = get_email_provider().sent[0]["link"].split("token=")[1]
    client.post("/auth/verify", json={"token": token})

    res = client.post("/auth/logout")

    assert res.status_code == 200
```

- [ ] **Step 7.2: Ajouter `method` au schema `LoginStartRequest`**

```python
# apps/api/app/modules/auth/schemas.py — remplacer LoginStartRequest
from typing import Literal
from pydantic import BaseModel, EmailStr


class LoginStartRequest(BaseModel):
    email: EmailStr
    method: Literal["magic_link", "otp"] = "magic_link"


class LoginStartResponse(BaseModel):
    ok: bool
    method: str


class LoginVerifyRequest(BaseModel):
    token: str


class LoginVerifyResponse(BaseModel):
    ok: bool
    session_created: bool
    redirect_to: str
```

- [ ] **Step 7.3: Brancher rate limiter + paramètre method dans le router**

```python
# apps/api/app/modules/auth/router.py — remplacer
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.modules.auth.rate_limit import login_start_limiter
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
    key = f"{request.client.host if request.client else 'unknown'}|{body.email}"
    login_start_limiter.check(key)
    return start_login(body.email, db, method=body.method)


@router.post("/verify", response_model=LoginVerifyResponse)
def login_verify(body: LoginVerifyRequest, response: Response, db: DbSession = Depends(get_db)):
    session = verify_token(body.token, db)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session.id,
        httponly=True,
        secure=False,  # True en prod derrière HTTPS — ici TestClient HTTP
        samesite="lax",
        max_age=SESSION_TTL_SECONDS,
    )
    return LoginVerifyResponse(ok=True, session_created=True, redirect_to="/portal")


@router.post("/logout")
def logout(response: Response, current_session=Depends(get_current_session)):
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}
```

- [ ] **Step 7.4: Run tous les tests auth**

Run: `cd apps/api && pytest tests/integration/test_auth_router.py -v`
Expected: 6 PASSED.

- [ ] **Step 7.5: Commit**

```bash
git add apps/api/app/modules/auth/ apps/api/tests/integration/test_auth_router.py
git commit -m "feat(api): wire auth endpoints with rate limiting and method selection"
```

---

## Task 8: Backend — session deps (TDD)

**Files:**
- Modify: `apps/api/app/shared/deps.py`
- Create: `apps/api/tests/integration/test_session_deps.py`

- [ ] **Step 8.1: Écrire les tests**

```python
# apps/api/tests/integration/test_session_deps.py
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.shared.deps import get_current_session, get_current_user
from app.shared.models import Session as SessionModel, User


def _setup(db_session):
    user = User(id="u1", email="test@example.com", display_name="T", kind="client", status="active")
    session = SessionModel(
        id="s1",
        user_id="u1",
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=1),
    )
    db_session.add_all([user, session])
    db_session.commit()
    return user, session


def test_no_cookie_returns_401(client):
    # Route de test éphémère
    @client.app.get("/_test/me")
    def _me(user=Depends(get_current_user)):
        return {"id": user.id}

    res = client.get("/_test/me")
    assert res.status_code == 401


def test_valid_session_returns_user(client, db_session):
    user, session = _setup(db_session)

    @client.app.get("/_test/me2")
    def _me(u=Depends(get_current_user)):
        return {"id": u.id}

    client.cookies.set("devgate_session", session.id)
    res = client.get("/_test/me2")
    assert res.status_code == 200
    assert res.json() == {"id": "u1"}


def test_expired_session_returns_401(client, db_session):
    user = User(id="u2", email="e@x.com", display_name="E", kind="client", status="active")
    session = SessionModel(
        id="s-exp",
        user_id="u2",
        expires_at=datetime.now(tz=timezone.utc) - timedelta(minutes=1),
    )
    db_session.add_all([user, session])
    db_session.commit()

    @client.app.get("/_test/me3")
    def _me(u=Depends(get_current_user)):
        return {"id": u.id}

    client.cookies.set("devgate_session", "s-exp")
    res = client.get("/_test/me3")
    assert res.status_code == 401
```

- [ ] **Step 8.2: Vérifier que `deps.py` gère bien les timezones**

Ouvrir `apps/api/app/shared/deps.py` et s'assurer que `get_current_session` compare bien avec UTC :

```python
# apps/api/app/shared/deps.py — remplacer get_current_session
from datetime import datetime, timezone
from fastapi import Cookie, Depends
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.shared.exceptions import ForbiddenException, SessionExpiredException, UnauthorizedException
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
        raise UnauthorizedException()  # 401 au lieu de SessionExpired pour le middleware

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
    return user


def require_agency_admin(user: User = Depends(get_current_user)) -> User:
    has_admin_grant = any(g.role == "agency_admin" and not g.revoked_at for g in user.grants)
    if not has_admin_grant and user.kind != "agency":
        raise ForbiddenException("Réservé aux administrateurs agence")
    return user
```

- [ ] **Step 8.3: Run tests**

Run: `cd apps/api && pytest tests/integration/test_session_deps.py -v`
Expected: 3 PASSED.

- [ ] **Step 8.4: Commit**

```bash
git add apps/api/app/shared/deps.py apps/api/tests/integration/test_session_deps.py
git commit -m "feat(api): harden session deps with timezone-safe expiry check"
```

---

## Task 9: Backend — migration initiale Alembic

**Files:**
- Create: `apps/api/app/migrations/versions/0001_initial.py`

- [ ] **Step 9.1: Générer automatiquement la migration depuis les modèles**

```bash
cd apps/api
# S'assurer que Postgres tourne
docker compose up db -d
# Attendre qu'il soit prêt
sleep 3
# Générer la migration
alembic revision --autogenerate -m "initial schema"
```

- [ ] **Step 9.2: Vérifier le fichier généré**

Le fichier `apps/api/app/migrations/versions/xxxxx_initial_schema.py` doit contenir les 9 tables : `users`, `organizations`, `projects`, `environments`, `access_grants`, `sessions`, `login_challenges`, `audit_events`, `tunnel_health_snapshots`.

- [ ] **Step 9.3: Renommer le fichier pour versioning explicite**

```bash
cd apps/api/app/migrations/versions
mv *initial_schema.py 0001_initial.py
# Mettre à jour la revision dans l'en-tête du fichier si besoin
```

- [ ] **Step 9.4: Appliquer la migration**

Run: `cd apps/api && alembic upgrade head`
Expected: `INFO [alembic.runtime.migration] Running upgrade -> 0001, initial schema`.

- [ ] **Step 9.5: Vérifier avec psql**

Run: `docker compose exec db psql -U devgate -d devgate -c "\dt"`
Expected: les 9 tables listées.

- [ ] **Step 9.6: Commit**

```bash
git add apps/api/app/migrations/versions/0001_initial.py
git commit -m "feat(api): add initial Alembic migration for core domain"
```

---

## Task 10: Backend — seed minimal pour dev

**Files:**
- Create: `apps/api/app/seeds.py`

- [ ] **Step 10.1: Créer le seed**

```python
# apps/api/app/seeds.py
"""Seed minimal pour développement local.
Run: python -m app.seeds
"""
from datetime import datetime, timezone

from app.database import SessionLocal
from app.shared.models import (
    AccessGrant, Environment, Organization, Project, User,
)


def seed():
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            print("Seed déjà présent, skip.")
            return

        # Admin agence
        admin = User(
            email="admin@agence.fr",
            display_name="Admin Agence",
            kind="agency",
            status="active",
        )
        db.add(admin)
        db.flush()

        # Client + grant admin
        org = Organization(name="Agence", slug="agence", branding_name="Agence")
        db.add(org)
        db.flush()

        db.add(AccessGrant(user_id=admin.id, organization_id=org.id, role="agency_admin"))

        # Client démo
        client_org = Organization(name="Client X", slug="client-x")
        db.add(client_org)
        db.flush()

        project = Project(
            organization_id=client_org.id,
            name="Refonte site",
            slug="refonte-site",
        )
        db.add(project)
        db.flush()

        env = Environment(
            project_id=project.id,
            name="Staging principal",
            slug="staging",
            kind="staging",
            public_hostname="client-x-staging.devgate.local",
            upstream_hostname="example-upstream.cfargotunnel.com",
            requires_app_auth=True,
            status="active",
        )
        db.add(env)

        # User client
        client_user = User(
            email="marie@client-x.com",
            display_name="Marie Chevalier",
            kind="client",
            status="active",
        )
        db.add(client_user)
        db.flush()
        db.add(AccessGrant(user_id=client_user.id, organization_id=client_org.id, role="client_member"))

        db.commit()
        print("✅ Seed créé : admin@agence.fr + marie@client-x.com")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
```

- [ ] **Step 10.2: Exécuter le seed**

Run: `cd apps/api && python -m app.seeds`
Expected: `✅ Seed créé : admin@agence.fr + marie@client-x.com`.

- [ ] **Step 10.3: Vérifier en base**

Run: `docker compose exec db psql -U devgate -d devgate -c "SELECT email, kind FROM users;"`
Expected: 2 lignes.

- [ ] **Step 10.4: Commit**

```bash
git add apps/api/app/seeds.py
git commit -m "feat(api): add minimal dev seed with agency admin and demo client"
```

---

## Task 11: Frontend — Vitest + setup

**Files:**
- Create: `apps/web/vitest.config.ts`
- Create: `apps/web/src/test/setup.ts`
- Modify: `apps/web/package.json` (scripts déjà scaffolded)

- [ ] **Step 11.1: Créer la config Vitest**

```typescript
// apps/web/vitest.config.ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
```

- [ ] **Step 11.2: Créer le setup**

```typescript
// apps/web/src/test/setup.ts
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup());
```

- [ ] **Step 11.3: Ajouter `@testing-library/jest-dom` aux deps**

Modifier `apps/web/package.json` pour ajouter dans `devDependencies` :
```json
"@testing-library/jest-dom": "^6.6.0"
```

Run: `cd apps/web && npm install`
Expected: install OK.

- [ ] **Step 11.4: Test sanity**

Créer un test minimal :
```typescript
// apps/web/src/test/sanity.test.ts
import { describe, it, expect } from "vitest";

describe("sanity", () => {
  it("runs", () => {
    expect(1 + 1).toBe(2);
  });
});
```

Run: `cd apps/web && npm run test`
Expected: 1 PASSED.

- [ ] **Step 11.5: Commit**

```bash
git add apps/web/vitest.config.ts apps/web/src/test/ apps/web/package.json apps/web/package-lock.json
git commit -m "test(web): setup Vitest and Testing Library"
```

---

## Task 12: Frontend — design tokens + globals.css

**Files:**
- Modify: `apps/web/src/app/globals.css`

- [ ] **Step 12.1: Remplacer `globals.css` par les tokens complets du mockup**

```css
/* apps/web/src/app/globals.css */
@import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap");

:root {
  --color-bg:          #f4f6fa;
  --color-surface:     #ffffff;
  --color-surface-2:   #f0f2f7;
  --color-border:      #e2e6ef;
  --color-text:        #111827;
  --color-text-muted:  #6b7280;
  --color-text-subtle: #9ca3af;
  --color-primary:     #2563eb;
  --color-primary-h:   #1d4ed8;
  --color-primary-s:   #eff6ff;
  --color-success:     #16a34a;
  --color-success-bg:  #dcfce7;
  --color-warning:     #d97706;
  --color-warning-bg:  #fef3c7;
  --color-danger:      #dc2626;
  --color-danger-bg:   #fee2e2;
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --radius-xl: 24px;
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.08);
  --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.10);
  --shadow-lg: 0 8px 40px rgba(0, 0, 0, 0.14);
  --font: 'Inter', system-ui, sans-serif;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html { height: 100%; }

body {
  min-height: 100%;
  font-family: var(--font);
  background: var(--color-bg);
  color: var(--color-text);
  -webkit-font-smoothing: antialiased;
}

a { color: inherit; text-decoration: none; }

button { font-family: inherit; }

input { font-family: inherit; }

.auth-standalone-bg {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  background:
    radial-gradient(ellipse 80% 60% at 60% -10%, rgba(37, 99, 235, 0.15) 0%, transparent 70%),
    radial-gradient(ellipse 60% 50% at -10% 80%, rgba(139, 92, 246, 0.10) 0%, transparent 60%),
    var(--color-bg);
}
```

- [ ] **Step 12.2: Commit**

```bash
git add apps/web/src/app/globals.css
git commit -m "style(web): add DevGate design tokens and auth background"
```

---

## Task 13: Frontend — composants partagés Button + AuthCard

**Files:**
- Create: `apps/web/src/components/shared/Button.tsx`
- Create: `apps/web/src/components/shared/Button.module.css`
- Create: `apps/web/src/components/auth/AuthCard.tsx`
- Create: `apps/web/src/components/auth/AuthCard.module.css`

- [ ] **Step 13.1: Button component**

```tsx
// apps/web/src/components/shared/Button.tsx
import type { ButtonHTMLAttributes, ReactNode } from "react";
import styles from "./Button.module.css";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "link";
  children: ReactNode;
}

export function Button({ variant = "primary", className, children, ...rest }: Props) {
  const cls = [styles.btn, styles[variant], className].filter(Boolean).join(" ");
  return (
    <button className={cls} {...rest}>
      {children}
    </button>
  );
}
```

```css
/* apps/web/src/components/shared/Button.module.css */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 11px 20px;
  font-size: 14px;
  font-weight: 600;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background 0.14s, color 0.14s, border-color 0.14s;
  width: 100%;
}

.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.primary { background: var(--color-primary); color: #fff; }
.primary:hover:not(:disabled) { background: var(--color-primary-h); }

.secondary {
  background: var(--color-surface-2);
  color: var(--color-text-muted);
  border: 1px solid var(--color-border);
  font-weight: 500;
}
.secondary:hover:not(:disabled) { background: var(--color-border); color: var(--color-text); }

.link {
  background: none;
  color: var(--color-primary);
  width: auto;
  padding: 0;
  font-size: 13px;
}
.link:hover:not(:disabled) { text-decoration: underline; }
```

- [ ] **Step 13.2: AuthCard component**

```tsx
// apps/web/src/components/auth/AuthCard.tsx
import type { ReactNode } from "react";
import styles from "./AuthCard.module.css";

interface Props {
  children: ReactNode;
  footer?: ReactNode;
}

export function AuthCard({ children, footer }: Props) {
  return (
    <div className={styles.card}>
      <div className={styles.brand}>
        <div className={styles.logo}>AG</div>
        <div className={styles.name}>
          {process.env.NEXT_PUBLIC_AGENCY_NAME ?? "Agence"}
        </div>
      </div>
      {children}
      {footer && <div className={styles.footer}>{footer}</div>}
    </div>
  );
}
```

```css
/* apps/web/src/components/auth/AuthCard.module.css */
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  width: 100%;
  max-width: 440px;
  padding: 48px 40px 40px;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 28px;
}

.logo {
  width: 36px; height: 36px;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, var(--color-primary), #7c3aed);
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 15px; font-weight: 700;
}

.name { font-size: 15px; font-weight: 700; }

.footer {
  margin-top: 24px; padding-top: 20px;
  border-top: 1px solid var(--color-border);
  text-align: center; font-size: 12px; color: var(--color-text-subtle);
}
```

- [ ] **Step 13.3: Commit**

```bash
git add apps/web/src/components/shared/ apps/web/src/components/auth/AuthCard.*
git commit -m "feat(web): add Button and AuthCard shared components"
```

---

## Task 14: Frontend — layout (auth) route group

**Files:**
- Create: `apps/web/src/app/(auth)/layout.tsx`

- [ ] **Step 14.1: Créer le layout**

```tsx
// apps/web/src/app/(auth)/layout.tsx
import type { ReactNode } from "react";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return <div className="auth-standalone-bg">{children}</div>;
}
```

- [ ] **Step 14.2: Commit**

```bash
git add apps/web/src/app/\(auth\)/layout.tsx
git commit -m "feat(web): add auth route group layout with atmospheric background"
```

---

## Task 15: Frontend — E01 Login page (TDD)

**Files:**
- Create: `apps/web/src/app/(auth)/login/__tests__/LoginPage.test.tsx`
- Modify: `apps/web/src/app/(auth)/login/page.tsx`
- Modify: `apps/web/src/app/(auth)/login/page.module.css` (create)

- [ ] **Step 15.1: Écrire le test**

```tsx
// apps/web/src/app/(auth)/login/__tests__/LoginPage.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LoginPage from "../page";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

const startMock = vi.fn();
vi.mock("@/lib/api/client", () => ({
  authApi: { start: (...args: unknown[]) => startMock(...args) },
}));

beforeEach(() => {
  pushMock.mockReset();
  startMock.mockReset();
});

describe("LoginPage (E01)", () => {
  it("renders email input and both buttons", () => {
    render(<LoginPage />);
    expect(screen.getByLabelText(/adresse email/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /recevoir mon lien/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /code otp/i })).toBeInTheDocument();
  });

  it("calls authApi.start with magic_link on submit", async () => {
    startMock.mockResolvedValue({ ok: true, method: "magic_link" });
    render(<LoginPage />);
    await userEvent.type(screen.getByLabelText(/adresse email/i), "user@example.com");
    await userEvent.click(screen.getByRole("button", { name: /recevoir mon lien/i }));
    await waitFor(() => expect(startMock).toHaveBeenCalledWith("user@example.com"));
    expect(pushMock).toHaveBeenCalledWith("/magic-sent?email=user%40example.com");
  });

  it("shows error on API failure", async () => {
    startMock.mockRejectedValue(new Error("Network down"));
    render(<LoginPage />);
    await userEvent.type(screen.getByLabelText(/adresse email/i), "user@example.com");
    await userEvent.click(screen.getByRole("button", { name: /recevoir mon lien/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/network down/i);
    });
  });

  it("switches to OTP route on secondary button", async () => {
    render(<LoginPage />);
    await userEvent.type(screen.getByLabelText(/adresse email/i), "user@example.com");
    await userEvent.click(screen.getByRole("button", { name: /code otp/i }));
    expect(pushMock).toHaveBeenCalledWith("/otp?email=user%40example.com");
  });
});
```

- [ ] **Step 15.2: Run — doit échouer (UI incomplète)**

Run: `cd apps/web && npm run test -- LoginPage`
Expected: FAIL (labels/boutons absents).

- [ ] **Step 15.3: Implémenter la page**

```tsx
// apps/web/src/app/(auth)/login/page.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api/client";
import { AuthCard } from "@/components/auth/AuthCard";
import { Button } from "@/components/shared/Button";
import styles from "./page.module.css";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submitMagicLink(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await authApi.start(email);
      router.push(`/magic-sent?email=${encodeURIComponent(email)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inattendue");
    } finally {
      setLoading(false);
    }
  }

  function useOtp() {
    router.push(`/otp?email=${encodeURIComponent(email)}`);
  }

  return (
    <AuthCard footer="Accès sécurisé · Aucun mot de passe · DevGate">
      <h1 className={styles.title}>Accéder à votre espace</h1>
      <p className={styles.sub}>
        Saisissez votre email professionnel pour recevoir un lien de connexion sécurisé.
      </p>
      <form onSubmit={submitMagicLink} noValidate>
        <label htmlFor="email" className={styles.label}>Adresse email</label>
        <input
          id="email"
          type="email"
          className={styles.input}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="vous@example.com"
          autoComplete="email"
          required
        />
        {error && <p role="alert" className={styles.error}>{error}</p>}
        <Button type="submit" disabled={loading}>
          {loading ? "Envoi…" : "Recevoir mon lien sécurisé"}
        </Button>
      </form>
      <div className={styles.divider}>ou</div>
      <Button type="button" variant="secondary" onClick={useOtp}>
        Utiliser un code OTP
      </Button>
    </AuthCard>
  );
}
```

```css
/* apps/web/src/app/(auth)/login/page.module.css */
.title { font-size: 22px; font-weight: 700; letter-spacing: -0.3px; margin-bottom: 6px; }
.sub { font-size: 14px; color: var(--color-text-muted); line-height: 1.55; margin-bottom: 28px; }
.label { display: block; font-size: 12px; font-weight: 600; margin-bottom: 5px; }
.input {
  width: 100%; padding: 10px 14px;
  background: var(--color-surface-2);
  border: 1.5px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 14px; color: var(--color-text);
  outline: none; transition: border-color 0.14s;
}
.input:focus { border-color: var(--color-primary); box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1); }
.error { color: var(--color-danger); font-size: 13px; margin-top: 8px; }
.divider {
  display: flex; align-items: center; gap: 10px;
  margin: 18px 0; font-size: 12px; color: var(--color-text-subtle);
}
.divider::before, .divider::after { content: ""; flex: 1; height: 1px; background: var(--color-border); }
```

- [ ] **Step 15.4: Run — tests passent**

Run: `cd apps/web && npm run test -- LoginPage`
Expected: 4 PASSED.

- [ ] **Step 15.5: Commit**

```bash
git add apps/web/src/app/\(auth\)/login/
git commit -m "feat(web): implement E01 Login page with tests"
```

---

## Task 16: Frontend — E02 Magic link sent

**Files:**
- Modify: `apps/web/src/app/(auth)/magic-sent/MagicSentContent.tsx`
- Create: `apps/web/src/components/auth/StateCard.tsx`
- Create: `apps/web/src/components/auth/StateCard.module.css`

- [ ] **Step 16.1: Créer StateCard réutilisable**

```tsx
// apps/web/src/components/auth/StateCard.tsx
import type { ReactNode } from "react";
import styles from "./StateCard.module.css";

interface Props {
  icon: ReactNode;
  tone: "ok" | "warn" | "danger" | "info";
  title: string;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
}

export function StateCard({ icon, tone, title, description, children, footer }: Props) {
  return (
    <div className={styles.card}>
      <div className={`${styles.icon} ${styles[tone]}`}>{icon}</div>
      <h1 className={styles.title}>{title}</h1>
      {description && <p className={styles.desc}>{description}</p>}
      {children && <div className={styles.body}>{children}</div>}
      {footer && <p className={styles.footer}>{footer}</p>}
    </div>
  );
}
```

```css
/* apps/web/src/components/auth/StateCard.module.css */
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  width: 100%; max-width: 480px;
  padding: 48px 40px 40px;
  text-align: center;
}

.icon {
  width: 64px; height: 64px;
  border-radius: 50%;
  margin: 0 auto 20px;
  display: flex; align-items: center; justify-content: center;
  font-size: 26px;
}
.ok      { background: var(--color-success-bg); }
.warn    { background: var(--color-warning-bg); }
.danger  { background: var(--color-danger-bg); }
.info    { background: var(--color-primary-s); }

.title { font-size: 22px; font-weight: 700; margin-bottom: 10px; }
.desc { font-size: 14px; color: var(--color-text-muted); line-height: 1.6; margin-bottom: 24px; }
.body { display: flex; flex-direction: column; gap: 10px; }
.footer { margin-top: 16px; font-size: 12px; color: var(--color-text-subtle); }
```

- [ ] **Step 16.2: Remplacer MagicSentContent**

```tsx
// apps/web/src/app/(auth)/magic-sent/MagicSentContent.tsx
"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { StateCard } from "@/components/auth/StateCard";
import { Button } from "@/components/shared/Button";
import { authApi } from "@/lib/api/client";

export default function MagicSentContent() {
  const params = useSearchParams();
  const router = useRouter();
  const email = params.get("email") ?? "";

  async function resend() {
    if (email) {
      await authApi.start(email).catch(() => {});
    }
  }

  return (
    <StateCard
      icon="✉️"
      tone="ok"
      title="Vérifiez vos emails"
      description={
        <>
          Un lien de connexion a été envoyé à <strong>{email || "votre email"}</strong>.
          Cliquez dessus pour accéder à votre espace.
        </>
      }
      footer="Le lien expire dans 15 minutes · Usage unique"
    >
      <Button onClick={resend}>Renvoyer le lien</Button>
      <Button
        variant="secondary"
        onClick={() => router.push(`/otp?email=${encodeURIComponent(email)}`)}
      >
        Utiliser un code OTP
      </Button>
      <Button variant="link" onClick={() => router.push("/login")}>
        Modifier l&apos;adresse
      </Button>
    </StateCard>
  );
}
```

- [ ] **Step 16.3: Commit**

```bash
git add apps/web/src/components/auth/StateCard.* apps/web/src/app/\(auth\)/magic-sent/
git commit -m "feat(web): implement E02 MagicSent and StateCard component"
```

---

## Task 17: Frontend — E03 OTP avec OtpInput (TDD)

**Files:**
- Create: `apps/web/src/components/auth/OtpInput.tsx`
- Create: `apps/web/src/components/auth/OtpInput.module.css`
- Create: `apps/web/src/components/auth/__tests__/OtpInput.test.tsx`
- Modify: `apps/web/src/app/(auth)/otp/OtpContent.tsx`
- Create: `apps/web/src/app/(auth)/otp/__tests__/OtpContent.test.tsx`

- [ ] **Step 17.1: Écrire le test OtpInput**

```tsx
// apps/web/src/components/auth/__tests__/OtpInput.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OtpInput } from "../OtpInput";

describe("OtpInput", () => {
  it("renders 6 inputs", () => {
    render(<OtpInput value="" onChange={() => {}} />);
    expect(screen.getAllByRole("textbox")).toHaveLength(6);
  });

  it("calls onChange with concatenated value on typing", async () => {
    const onChange = vi.fn();
    render(<OtpInput value="" onChange={onChange} />);
    const inputs = screen.getAllByRole("textbox");
    await userEvent.type(inputs[0], "1");
    expect(onChange).toHaveBeenLastCalledWith("1");
  });

  it("accepts only digits", async () => {
    const onChange = vi.fn();
    render(<OtpInput value="" onChange={onChange} />);
    const inputs = screen.getAllByRole("textbox");
    await userEvent.type(inputs[0], "a");
    expect(onChange).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 17.2: Run — doit échouer (module absent)**

Run: `cd apps/web && npm run test -- OtpInput`
Expected: FAIL / module not found.

- [ ] **Step 17.3: Implémenter OtpInput**

```tsx
// apps/web/src/components/auth/OtpInput.tsx
"use client";

import { useRef, useEffect } from "react";
import styles from "./OtpInput.module.css";

interface Props {
  value: string;
  onChange: (val: string) => void;
  length?: number;
}

export function OtpInput({ value, onChange, length = 6 }: Props) {
  const refs = useRef<Array<HTMLInputElement | null>>([]);

  useEffect(() => {
    if (value.length < length) {
      refs.current[value.length]?.focus();
    }
  }, [value, length]);

  function handleChange(i: number, char: string) {
    const digit = char.replace(/\D/g, "").slice(0, 1);
    if (!digit && char !== "") return;
    const next = value.substring(0, i) + digit + value.substring(i + 1);
    onChange(next.slice(0, length));
  }

  function handleKeyDown(i: number, e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Backspace" && !value[i] && i > 0) {
      refs.current[i - 1]?.focus();
    }
  }

  return (
    <div className={styles.group}>
      {Array.from({ length }).map((_, i) => (
        <input
          key={i}
          type="text"
          inputMode="numeric"
          role="textbox"
          maxLength={1}
          className={`${styles.input} ${value[i] ? styles.filled : ""}`}
          value={value[i] ?? ""}
          onChange={(e) => handleChange(i, e.target.value)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          ref={(el) => { refs.current[i] = el; }}
          aria-label={`Chiffre ${i + 1}`}
        />
      ))}
    </div>
  );
}
```

```css
/* apps/web/src/components/auth/OtpInput.module.css */
.group { display: flex; gap: 10px; justify-content: center; margin: 20px 0 24px; }
.input {
  width: 52px; height: 60px;
  text-align: center;
  font-size: 22px; font-weight: 700;
  background: var(--color-surface-2);
  border: 2px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text);
  outline: none;
  transition: border-color 0.14s;
}
.input:focus { border-color: var(--color-primary); }
.filled { border-color: var(--color-primary); background: var(--color-primary-s); }
```

- [ ] **Step 17.4: Tests OtpInput passent**

Run: `cd apps/web && npm run test -- OtpInput`
Expected: 3 PASSED.

- [ ] **Step 17.5: Écrire le test OtpContent**

```tsx
// apps/web/src/app/(auth)/otp/__tests__/OtpContent.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import OtpContent from "../OtpContent";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  useSearchParams: () => new URLSearchParams("email=user@example.com"),
}));

const verifyMock = vi.fn();
vi.mock("@/lib/api/client", () => ({
  authApi: { verify: (...args: unknown[]) => verifyMock(...args) },
}));

beforeEach(() => {
  pushMock.mockReset();
  verifyMock.mockReset();
});

describe("OtpContent (E03)", () => {
  it("renders 6 OTP inputs", () => {
    render(<OtpContent />);
    expect(screen.getAllByRole("textbox")).toHaveLength(6);
  });

  it("submits when 6 digits entered", async () => {
    verifyMock.mockResolvedValue({ ok: true, redirect_to: "/portal" });
    render(<OtpContent />);
    const inputs = screen.getAllByRole("textbox");
    for (let i = 0; i < 6; i++) {
      await userEvent.type(inputs[i], String(i));
    }
    await userEvent.click(screen.getByRole("button", { name: /valider/i }));
    await waitFor(() => expect(verifyMock).toHaveBeenCalledWith("012345"));
    expect(pushMock).toHaveBeenCalledWith("/portal");
  });

  it("shows error on invalid code", async () => {
    verifyMock.mockRejectedValue(new Error("Code invalide"));
    render(<OtpContent />);
    const inputs = screen.getAllByRole("textbox");
    for (let i = 0; i < 6; i++) {
      await userEvent.type(inputs[i], "1");
    }
    await userEvent.click(screen.getByRole("button", { name: /valider/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/code invalide/i);
    });
  });
});
```

- [ ] **Step 17.6: Remplacer OtpContent**

```tsx
// apps/web/src/app/(auth)/otp/OtpContent.tsx
"use client";

import { useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { authApi } from "@/lib/api/client";
import { AuthCard } from "@/components/auth/AuthCard";
import { OtpInput } from "@/components/auth/OtpInput";
import { Button } from "@/components/shared/Button";

export default function OtpContent() {
  const params = useSearchParams();
  const router = useRouter();
  const email = params.get("email") ?? "";
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await authApi.verify(code);
      router.push(res.redirect_to);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Code invalide");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthCard footer="Code à usage unique · Valable 10 minutes">
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 6 }}>Entrez votre code</h1>
      <p style={{ fontSize: 14, color: "var(--color-text-muted)", marginBottom: 20 }}>
        Un code à 6 chiffres a été envoyé à <strong>{email}</strong>.
      </p>
      <form onSubmit={submit} noValidate>
        <OtpInput value={code} onChange={setCode} />
        {error && <p role="alert" style={{ color: "var(--color-danger)", fontSize: 13, marginBottom: 12 }}>{error}</p>}
        <Button type="submit" disabled={loading || code.length !== 6}>
          {loading ? "Vérification…" : "Valider"}
        </Button>
      </form>
    </AuthCard>
  );
}
```

- [ ] **Step 17.7: Tests OtpContent passent**

Run: `cd apps/web && npm run test -- OtpContent`
Expected: 3 PASSED.

- [ ] **Step 17.8: Commit**

```bash
git add apps/web/src/components/auth/OtpInput.* apps/web/src/components/auth/__tests__/ apps/web/src/app/\(auth\)/otp/
git commit -m "feat(web): implement E03 OTP page with OtpInput component"
```

---

## Task 18: Frontend — E09 Link expired, E10 Session expired, E11 Access denied

**Files:**
- Modify: `apps/web/src/app/(auth)/link-expired/page.tsx`
- Modify: `apps/web/src/app/session-expired/page.tsx`
- Modify: `apps/web/src/app/access-denied/page.tsx`

- [ ] **Step 18.1: E09 Link expired**

```tsx
// apps/web/src/app/(auth)/link-expired/page.tsx
import Link from "next/link";
import { StateCard } from "@/components/auth/StateCard";
import { Button } from "@/components/shared/Button";

export default function LinkExpiredPage() {
  return (
    <StateCard
      icon="!"
      tone="danger"
      title="Ce lien n'est plus valide"
      description="Le lien de connexion a expiré ou a déjà été utilisé. Vous pouvez en demander un nouveau en quelques secondes."
    >
      <Link href="/login" style={{ width: "100%" }}>
        <Button>Recevoir un nouveau lien</Button>
      </Link>
    </StateCard>
  );
}
```

- [ ] **Step 18.2: E10 Session expired**

La page `/session-expired` est hors du groupe `(auth)` — il faut un layout minimal. Créer :

```tsx
// apps/web/src/app/session-expired/page.tsx
import Link from "next/link";
import { StateCard } from "@/components/auth/StateCard";
import { Button } from "@/components/shared/Button";

export default function SessionExpiredPage() {
  return (
    <div className="auth-standalone-bg">
      <StateCard
        icon="⏱"
        tone="warn"
        title="Votre session a expiré"
        description="Vous avez été déconnecté automatiquement après 7 jours. Votre compte est intact, reconnectez-vous pour retrouver vos ressources."
        footer="Pas de panique — vos accès sont conservés."
      >
        <Link href="/login" style={{ width: "100%" }}>
          <Button>Se reconnecter</Button>
        </Link>
      </StateCard>
    </div>
  );
}
```

- [ ] **Step 18.3: E11 Access denied**

```tsx
// apps/web/src/app/access-denied/page.tsx
import Link from "next/link";
import { StateCard } from "@/components/auth/StateCard";
import { Button } from "@/components/shared/Button";

export default function AccessDeniedPage() {
  return (
    <div className="auth-standalone-bg">
      <StateCard
        icon="✕"
        tone="danger"
        title="Accès non autorisé"
        description="Votre compte ne dispose pas d'un accès actif à cette ressource. Si vous pensez que c'est une erreur, contactez l'agence."
      >
        <Link href="/portal" style={{ width: "100%" }}>
          <Button>Retour à mon portail</Button>
        </Link>
        <Button variant="secondary">Contacter l&apos;agence</Button>
      </StateCard>
    </div>
  );
}
```

- [ ] **Step 18.4: Vérifier le rendu sans planter**

Run: `cd apps/web && npm run build`
Expected: Build OK, toutes les pages compilent.

- [ ] **Step 18.5: Commit**

```bash
git add apps/web/src/app/\(auth\)/link-expired/ apps/web/src/app/session-expired/ apps/web/src/app/access-denied/
git commit -m "feat(web): implement E09 E10 E11 error state pages"
```

---

## Task 19: Test manuel E2E local

**Files:** aucun

- [ ] **Step 19.1: Lancer la stack complète**

Run : `docker compose up` (depuis la racine).
Expected: `db`, `api`, `web` démarrent sans erreur.

- [ ] **Step 19.2: Vérifier l'API**

Run: `curl http://localhost:8000/healthz`
Expected: `{"ok": true}`.

- [ ] **Step 19.3: Tester le flow login dans le navigateur**

1. Ouvrir `http://localhost:3000`
2. Doit rediriger sur `/login`
3. Saisir `marie@client-x.com` (créé par le seed)
4. Cliquer "Recevoir mon lien sécurisé"
5. Doit arriver sur `/magic-sent?email=...`
6. Dans les logs de l'API, chercher le lien envoyé par `FakeEmailProvider` (ou inspecter la DB : `SELECT hashed_token FROM login_challenges`)
7. En dev, ajouter une route de debug ou imprimer le lien en console :

Ajouter temporairement dans `apps/api/app/modules/auth/service.py` après `provider.send_magic_link(...)` :
```python
import os
if os.environ.get("ENV") == "development":
    print(f"🔗 Magic link: {link}")
```

8. Copier ce lien, l'ouvrir → doit appeler `/auth/verify` et arriver sur `/portal` (404 attendu car pas encore implémenté — c'est le scope du Plan 2).

- [ ] **Step 19.4: Vérifier les audit events**

Run: `docker compose exec db psql -U devgate -d devgate -c "SELECT event_type, created_at FROM audit_events ORDER BY created_at;"`
Expected: `login.magic_link.requested`, `login.session.created` visibles.

- [ ] **Step 19.5: Retirer le print de debug, commit**

```bash
git add apps/api/app/modules/auth/service.py
git commit -m "chore: cleanup debug print after manual E2E validation"
```

---

## Task 20: Suite de tests complète + CI local

**Files:** aucun

- [ ] **Step 20.1: Lancer toute la suite backend**

Run: `cd apps/api && pytest -v`
Expected: tous les tests PASSED (auth service, audit, rate limit, email, session deps, auth router).

- [ ] **Step 20.2: Lancer toute la suite frontend**

Run: `cd apps/web && npm run test`
Expected: tous PASSED.

- [ ] **Step 20.3: Vérifier la couverture critique**

Checklist des invariants couverts :
- [x] email inconnu → réponse anti-enumeration
- [x] challenge expiré → 410
- [x] challenge déjà utilisé → 410
- [x] token invalide → 404
- [x] session expirée → 401
- [x] rate limit login start → 429
- [x] audit événements login présents
- [x] E01 soumission déclenche start
- [x] E03 OTP 6 chiffres déclenche verify

- [ ] **Step 20.4: Mettre à jour le README**

Modifier `README.md` à la racine pour ajouter :

```markdown
## Développement local

\`\`\`bash
# 1. Lancer la stack
docker compose up

# 2. Appliquer les migrations (première fois)
make migrate

# 3. Seed dev (admin + client démo)
make seed

# 4. Ouvrir http://localhost:3000
\`\`\`

### Tests

\`\`\`bash
make test       # API + Web
make test-api
make test-web
\`\`\`

### Comptes de démo (seed)
- Admin agence : `admin@agence.fr`
- Client : `marie@client-x.com`
```

- [ ] **Step 20.5: Commit final**

```bash
git add README.md
git commit -m "docs: document local dev setup and demo accounts"
```

---

## Definition of Done (Plan 1)

- [ ] Un user `marie@client-x.com` peut déclencher `/auth/start` et recevoir un magic link (dans `FakeEmailProvider.sent`)
- [ ] Le lien consommé via `/auth/verify` crée une session cookie HttpOnly
- [ ] Un challenge expiré ou réutilisé renvoie 410
- [ ] Un email inconnu renvoie `ok: true` sans créer de challenge (anti-enum)
- [ ] Tous les événements auth critiques sont en `audit_events`
- [ ] Les écrans E01, E02, E03, E09, E10, E11 sont visibles et pixel-proches des mockups
- [ ] Rate limit actif : 5 `/auth/start` par 10 min par IP+email
- [ ] `pytest -v` et `npm run test` tous verts
- [ ] `docker compose up` démarre la stack complète

---

## Ce qui reste hors scope Plan 1

Ces éléments seront traités dans les plans suivants :
- Portail `/me` et liste environnements → **Plan 2**
- Back-office agence → **Plan 3**
- Gateway proxy vers ressource → **Plan 4**
- Intégration Resend réelle (remplacement FakeEmailProvider) → **Plan 5 hardening**
- CSRF token sur `/auth/verify` → **Plan 5 hardening**

## Follow-ups découverts pendant l'exécution

Ces points sont remontés par les code reviews et doivent être traités en **Plan 5 hardening** :

### Security — timing side-channels (Task 4 review)
- `start_login()` a un delta de latence observable entre unknown email (fast) et known email (DB inserts + email send). L'anti-enumeration au niveau réponse est correct mais timing-leak-able. Fix : déplacer l'envoi email hors de la request path (background task / outbox).
- Email send est synchrone — si le provider plante, HTTP 500 + orphan challenge en base. Fix : try/except + audit `login.email.send_failed` + retour `{ok:True}` même en cas d'échec d'envoi.

### Config — hard-coded URLs (Task 4 review)
- `http://localhost:3000/verify?token=...` est en dur dans `service.py`. Fix : ajouter `FRONTEND_BASE_URL` dans `settings` (`config.py`) et l'utiliser pour construire le magic link.

### Privacy — audit metadata (Task 4 review)
- L'email brut est stocké dans `audit_events.metadata_json` pour le path `login.start.unknown_email`. RGPD concern. Fix : hash l'email ou le retirer (le `event_type` suffit comme signal).

### Test coverage gaps (Task 4 review)
- Pas de test pour `start_login(method="invalid")` (fall-through silencieux vers magic_link)
- Pas de test pour email provider qui lève une exception
- Pas de test pour case sensitivity sur `User.email`
- Pas de test d'assertion explicite que l'audit row `unknown_email` est persistée

Ces tests peuvent être ajoutés au Plan 5 hardening ou directement en début de Plan 2.
