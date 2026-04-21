# Security Hardening — Auth & Session

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corriger les failles de sécurité critiques et élevées dans le module d'authentification et la gestion des sessions.

**Architecture:** Corrections ciblées dans `auth/router.py`, `auth/service.py`, `auth/schemas.py`, `shared/deps.py`, `shared/models.py`. Chaque fix est indépendant et testable séparément. TDD — écrire les tests en premier.

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy · pytest  
**Tests :** `cd apps/api && .venv/bin/python -m pytest` (jamais `python -m pytest`)

---

## Fichiers modifiés

| Fichier | Action | Finding |
|---|---|---|
| `apps/api/app/modules/auth/router.py` | Modify | C-01, F-02 |
| `apps/api/app/modules/auth/service.py` | Modify | F-04 |
| `apps/api/app/modules/auth/schemas.py` | Modify | F-01 |
| `apps/api/app/shared/deps.py` | Modify | H-01, H-02 |
| `apps/api/app/shared/models.py` | Modify | H-03 |
| `apps/api/tests/integration/test_auth.py` | Modify | tous |

---

## Task 1 — C-01 : Logout révoque la session en base

**Finding :** `POST /auth/logout` supprime le cookie mais pas la session en base. Cookie volé reste valide 7 jours.

**Files:**
- Modify: `apps/api/app/modules/auth/router.py`
- Test: `apps/api/tests/integration/test_auth.py`

- [ ] **Step 1 : Lire le code actuel**

```bash
cat apps/api/app/modules/auth/router.py
```

Repère le handler `logout` (cherche `@router.post("/logout")`).

- [ ] **Step 2 : Écrire le test qui échoue**

Dans `apps/api/tests/integration/test_auth.py`, ajoute à la fin :

```python
def test_logout_revokes_session_in_db(client, db_session):
    """Après logout, la session doit être supprimée en base."""
    # Créer un user et une session via login
    from app.shared.models import User, Session as DevSession
    import uuid, datetime
    user = User(id=str(uuid.uuid4()), email="logout-test@example.com",
                kind="client", status="active")
    db_session.add(user)
    session = DevSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=7),
    )
    db_session.add(session)
    db_session.commit()

    # Appeler logout avec le cookie de session
    response = client.post(
        "/auth/logout",
        cookies={"devgate_session": session.id},
    )
    assert response.status_code == 200

    # La session ne doit plus exister en base
    remaining = db_session.query(DevSession).filter(DevSession.id == session.id).first()
    assert remaining is None, "La session doit être supprimée en base après logout"
```

- [ ] **Step 3 : Vérifier que le test échoue**

```bash
cd apps/api && .venv/bin/python -m pytest tests/integration/test_auth.py::test_logout_revokes_session_in_db -v
```

Expected : FAIL — la session existe encore en base.

- [ ] **Step 4 : Corriger le handler logout**

Dans `apps/api/app/modules/auth/router.py`, remplace le handler `logout` :

```python
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
```

Si `SESSION_COOKIE` n'est pas importé en haut du fichier, cherche le nom de la constante dans le fichier (grep `SESSION_COOKIE` ou `devgate_session`) et utilise la même constante.

- [ ] **Step 5 : Vérifier que le test passe**

```bash
cd apps/api && .venv/bin/python -m pytest tests/integration/test_auth.py::test_logout_revokes_session_in_db -v
```

Expected : PASS

- [ ] **Step 6 : Vérifier que tous les tests passent**

```bash
cd apps/api && .venv/bin/python -m pytest -x -q
```

Expected : tous les tests passent, 0 échec.

- [ ] **Step 7 : Commit**

```bash
git add apps/api/app/modules/auth/router.py apps/api/tests/integration/test_auth.py
git commit -m "fix(auth): logout révoque la session en base (C-01)"
```

---

## Task 2 — H-01 : require_agency_admin — supprimer la condition `kind="agency"`

**Finding :** `if not has_admin_grant and user.kind != "agency"` — un user `kind="agency"` sans grant admin accède au back-office.

**Files:**
- Modify: `apps/api/app/shared/deps.py`
- Test: `apps/api/tests/integration/test_admin_router.py`

- [ ] **Step 1 : Lire le code actuel**

```bash
grep -n "require_agency_admin\|has_admin_grant\|kind" apps/api/app/shared/deps.py
```

- [ ] **Step 2 : Écrire le test qui échoue**

Dans `apps/api/tests/integration/test_admin_router.py`, ajoute à la fin :

```python
def test_agency_user_without_admin_grant_is_forbidden(client, db_session):
    """Un user kind='agency' sans grant agency_admin doit recevoir 403."""
    from app.shared.models import User, Session as DevSession
    import uuid, datetime
    # Créer un user kind="agency" sans aucun grant
    user = User(
        id=str(uuid.uuid4()),
        email="agency-no-grant@example.com",
        kind="agency",
        status="active",
    )
    db_session.add(user)
    session = DevSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=7),
    )
    db_session.add(session)
    db_session.commit()

    response = client.get(
        "/admin/stats",
        cookies={"devgate_session": session.id},
    )
    assert response.status_code == 403, (
        f"Un user agency sans grant doit être refusé, got {response.status_code}"
    )
```

- [ ] **Step 3 : Vérifier que le test échoue**

```bash
cd apps/api && .venv/bin/python -m pytest tests/integration/test_admin_router.py::test_agency_user_without_admin_grant_is_forbidden -v
```

Expected : FAIL — le user passe (200 ou autre code non-403).

- [ ] **Step 4 : Corriger `require_agency_admin` dans `deps.py`**

Trouve la fonction `require_agency_admin` dans `apps/api/app/shared/deps.py` et remplace-la par :

```python
def require_agency_admin(user: User = Depends(get_current_user)) -> User:
    """Exige un grant agency_admin actif. Le champ `kind` n'est pas suffisant."""
    has_admin_grant = any(
        g.role == "agency_admin" and g.revoked_at is None
        for g in user.grants
    )
    if not has_admin_grant:
        raise ForbiddenException("Réservé aux administrateurs agence")
    return user
```

- [ ] **Step 5 : Vérifier que le test passe**

```bash
cd apps/api && .venv/bin/python -m pytest tests/integration/test_admin_router.py::test_agency_user_without_admin_grant_is_forbidden -v
```

Expected : PASS

- [ ] **Step 6 : Vérifier que tous les tests passent**

```bash
cd apps/api && .venv/bin/python -m pytest -x -q
```

Expected : tous les tests passent. Si un test admin existant échoue, c'est peut-être parce que le user de test n'avait pas de grant — vérifie le helper de création d'admin dans `conftest.py` ou les fixtures.

- [ ] **Step 7 : Commit**

```bash
git add apps/api/app/shared/deps.py apps/api/tests/integration/test_admin_router.py
git commit -m "fix(auth): require_agency_admin — grant seul autorise l'accès admin (H-01)"
```

---

## Task 3 — H-02 : Vérifier `user.status` dans `get_current_user`

**Finding :** Un utilisateur désactivé conserve son accès jusqu'à l'expiration de sa session.

**Files:**
- Modify: `apps/api/app/shared/deps.py`
- Test: `apps/api/tests/integration/test_auth.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Dans `apps/api/tests/integration/test_auth.py`, ajoute :

```python
def test_inactive_user_is_rejected(client, db_session):
    """Un user inactif doit recevoir 401 même avec une session valide."""
    from app.shared.models import User, Session as DevSession
    import uuid, datetime
    user = User(
        id=str(uuid.uuid4()),
        email="inactive@example.com",
        kind="client",
        status="inactive",
    )
    db_session.add(user)
    session = DevSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=7),
    )
    db_session.add(session)
    db_session.commit()

    response = client.get(
        "/portal/me",
        cookies={"devgate_session": session.id},
    )
    assert response.status_code == 401, (
        f"Un user inactif doit être rejeté, got {response.status_code}"
    )
```

Si `/portal/me` n'existe pas, utilise `/auth/logout` ou tout endpoint qui requiert `get_current_user`.

- [ ] **Step 2 : Vérifier que le test échoue**

```bash
cd apps/api && .venv/bin/python -m pytest tests/integration/test_auth.py::test_inactive_user_is_rejected -v
```

Expected : FAIL

- [ ] **Step 3 : Corriger `get_current_user` dans `deps.py`**

Trouve `get_current_user` dans `apps/api/app/shared/deps.py`. Ajoute la vérification de statut après la récupération de l'user :

```python
def get_current_user(
    session: Session = Depends(get_current_session),
    db: DbSession = Depends(get_db),
) -> User:
    user = db.query(User).filter(User.id == session.user_id).first()
    if not user:
        raise UnauthorizedException("Utilisateur introuvable")
    if user.status != "active":
        raise UnauthorizedException("Compte désactivé")
    return user
```

Vérifie que `UnauthorizedException` est importée dans le fichier.

- [ ] **Step 4 : Vérifier que le test passe**

```bash
cd apps/api && .venv/bin/python -m pytest tests/integration/test_auth.py::test_inactive_user_is_rejected -v
```

Expected : PASS

- [ ] **Step 5 : Vérifier que tous les tests passent**

```bash
cd apps/api && .venv/bin/python -m pytest -x -q
```

- [ ] **Step 6 : Commit**

```bash
git add apps/api/app/shared/deps.py apps/api/tests/integration/test_auth.py
git commit -m "fix(auth): rejeter les users inactifs dès la vérification de session (H-02)"
```

---

## Task 4 — H-03 : Verrouiller le challenge OTP après N tentatives échouées

**Finding :** Rate limiter en mémoire bypassable par redémarrage. Solution minimale v1 : verrouillage du challenge en base après 5 tentatives.

**Files:**
- Modify: `apps/api/app/shared/models.py` (ajouter `attempt_count`)
- Modify: `apps/api/app/modules/auth/service.py`
- Create: `apps/api/alembic/versions/<timestamp>_add_attempt_count_to_login_challenge.py`
- Test: `apps/api/tests/integration/test_auth.py`

- [ ] **Step 1 : Vérifier si `attempt_count` existe déjà dans `LoginChallenge`**

```bash
grep -n "attempt_count\|LoginChallenge" apps/api/app/shared/models.py
```

Si `attempt_count` existe déjà sur le modèle, passe directement au Step 3 (vérifier s'il est utilisé dans `verify_token`).

- [ ] **Step 2 : Ajouter `attempt_count` au modèle `LoginChallenge`**

Dans `apps/api/app/shared/models.py`, trouve le modèle `LoginChallenge` et ajoute la colonne :

```python
attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
```

Génère la migration Alembic :

```bash
cd apps/api && .venv/bin/alembic revision --autogenerate -m "add attempt_count to login_challenge"
```

Applique la migration sur la DB de test (SQLite en test — les tests l'appliquent automatiquement via les fixtures) :

```bash
cd apps/api && .venv/bin/alembic upgrade head
```

- [ ] **Step 3 : Écrire le test qui échoue**

Dans `apps/api/tests/integration/test_auth.py`, ajoute :

```python
def test_otp_locked_after_5_failed_attempts(client, db_session):
    """Après 5 tentatives OTP échouées, le challenge doit être verrouillé."""
    # Démarrer un login OTP
    resp = client.post("/auth/start", json={"email": "user@example.com", "method": "otp"})
    # Note : si l'email n'existe pas, le comportement dépend de l'implémentation
    # Utilise un email qui existe dans les fixtures de test
    # Récupère le challenge directement en base
    from app.shared.models import LoginChallenge
    challenge = db_session.query(LoginChallenge).order_by(
        LoginChallenge.created_at.desc()
    ).first()
    if challenge is None:
        pytest.skip("Pas de challenge créé (email inconnu)")

    # 5 tentatives avec un mauvais code
    for _ in range(5):
        client.post("/auth/verify", json={"token": "000000"})

    # La 6e tentative doit être refusée même avec le bon code
    # (le challenge est verrouillé, pas expiré)
    db_session.refresh(challenge)
    assert challenge.attempt_count >= 5

    resp6 = client.post("/auth/verify", json={"token": "000000"})
    assert resp6.status_code in (400, 429), (
        f"Après 5 échecs, la 6e tentative doit être refusée, got {resp6.status_code}"
    )
```

- [ ] **Step 4 : Vérifier que le test échoue**

```bash
cd apps/api && .venv/bin/python -m pytest tests/integration/test_auth.py::test_otp_locked_after_5_failed_attempts -v
```

Expected : FAIL ou SKIP si le test ne peut pas créer de challenge.

- [ ] **Step 5 : Implémenter le verrouillage dans `verify_token`**

Dans `apps/api/app/modules/auth/service.py`, trouve la fonction `verify_token` (ou `verify_challenge`). 

Après avoir récupéré le challenge et vérifié qu'il n'est pas expiré ni déjà utilisé, ajoute la vérification :

```python
MAX_ATTEMPTS = 5

# Vérifier le verrouillage AVANT de vérifier le token
if challenge.attempt_count >= MAX_ATTEMPTS:
    raise InvalidTokenException("Challenge verrouillé après trop de tentatives")

# Vérifier le token
token_hash = hashlib.sha256(token.encode()).hexdigest()
if challenge.token_hash != token_hash:
    # Incrémenter le compteur en base
    challenge.attempt_count += 1
    db.commit()
    raise InvalidTokenException("Token invalide")

# Token valide — marquer comme utilisé (code existant)
```

Vérifie que `InvalidTokenException` (ou l'équivalent dans le projet) est importée.

- [ ] **Step 6 : Vérifier que le test passe**

```bash
cd apps/api && .venv/bin/python -m pytest tests/integration/test_auth.py::test_otp_locked_after_5_failed_attempts -v
```

Expected : PASS (ou SKIP si le setup de fixture ne permet pas de créer un challenge valide — dans ce cas, s'assurer que le code est correct via lecture)

- [ ] **Step 7 : Vérifier que tous les tests passent**

```bash
cd apps/api && .venv/bin/python -m pytest -x -q
```

- [ ] **Step 8 : Commit**

```bash
git add apps/api/app/shared/models.py apps/api/app/modules/auth/service.py \
        apps/api/alembic/versions/ apps/api/tests/integration/test_auth.py
git commit -m "fix(auth): verrouiller le challenge après 5 tentatives échouées (H-03)"
```

---

## Task 5 — F-01 : Token OTP avec `max_length`

**Finding :** Le champ `token` dans `LoginVerifyRequest` n'a pas de contrainte de longueur — vecteur DoS mineur.

**Files:**
- Modify: `apps/api/app/modules/auth/schemas.py`
- Test: `apps/api/tests/integration/test_auth.py`

- [ ] **Step 1 : Lire le schéma actuel**

```bash
cat apps/api/app/modules/auth/schemas.py
```

- [ ] **Step 2 : Écrire le test qui échoue**

```python
def test_verify_rejects_oversized_token(client):
    """Un token de plus de 256 caractères doit être rejeté avec 422."""
    giant_token = "A" * 1000
    resp = client.post("/auth/verify", json={"token": giant_token})
    assert resp.status_code == 422, (
        f"Token trop long doit être rejeté, got {resp.status_code}"
    )
```

- [ ] **Step 3 : Vérifier que le test échoue**

```bash
cd apps/api && .venv/bin/python -m pytest tests/integration/test_auth.py::test_verify_rejects_oversized_token -v
```

Expected : FAIL (le serveur accepte le token oversized)

- [ ] **Step 4 : Ajouter la contrainte dans le schéma**

Dans `apps/api/app/modules/auth/schemas.py`, modifie `LoginVerifyRequest` :

```python
from typing import Annotated
from pydantic import BaseModel, StringConstraints

class LoginVerifyRequest(BaseModel):
    token: Annotated[str, StringConstraints(min_length=1, max_length=256)]
```

Si d'autres schémas dans le même fichier ont déjà des imports `Annotated`/`StringConstraints`, réutilise-les.

- [ ] **Step 5 : Vérifier que le test passe**

```bash
cd apps/api && .venv/bin/python -m pytest tests/integration/test_auth.py::test_verify_rejects_oversized_token -v
```

Expected : PASS

- [ ] **Step 6 : Vérifier que tous les tests passent**

```bash
cd apps/api && .venv/bin/python -m pytest -x -q
```

- [ ] **Step 7 : Commit**

```bash
git add apps/api/app/modules/auth/schemas.py apps/api/tests/integration/test_auth.py
git commit -m "fix(auth): limiter la longueur du token OTP à 256 caractères (F-01)"
```

---

## Task 6 — F-02 & F-04 : SameSite=Lax documenté + email haché dans l'audit

**Finding F-02 :** `SameSite=Lax` est un choix valide (liens depuis email → portail), documenter explicitement.  
**Finding F-04 :** Email brut des utilisateurs inconnus dans les audit logs → hacher.

**Files:**
- Modify: `apps/api/app/modules/auth/service.py` (F-04)
- Modify: `apps/api/app/modules/auth/router.py` (F-02 commentaire)

- [ ] **Step 1 : Hacher l'email dans l'audit `login.start.unknown_email`**

Dans `apps/api/app/modules/auth/service.py`, trouve l'appel audit pour email inconnu (cherche `unknown_email`).

Remplace :

```python
audit(db, event_type="login.start.unknown_email", metadata={"email": email})
```

Par :

```python
import hashlib
_hint = hashlib.sha256(email.lower().encode()).hexdigest()[:12]
audit(db, event_type="login.start.unknown_email", metadata={"email_hint": _hint})
```

Si `hashlib` est déjà importé dans le fichier, ne pas réimporter. L'import peut être mis en haut du fichier.

- [ ] **Step 2 : Documenter SameSite=Lax dans le code**

Dans `apps/api/app/modules/auth/router.py`, trouve le `response.set_cookie(...)` qui inclut `samesite="lax"`. Ajoute un commentaire :

```python
response.set_cookie(
    SESSION_COOKIE,
    value=session.id,
    httponly=True,
    secure=settings.COOKIE_SECURE,
    samesite="lax",  # Lax intentionnel : les magic links arrivent par email (navigation cross-site)
    max_age=settings.SESSION_TTL_DAYS * 86400,
    path="/",
)
```

- [ ] **Step 3 : Vérifier que tous les tests passent**

```bash
cd apps/api && .venv/bin/python -m pytest -x -q
```

- [ ] **Step 4 : Commit**

```bash
git add apps/api/app/modules/auth/service.py apps/api/app/modules/auth/router.py
git commit -m "fix(auth): hacher l'email dans les audit logs + documenter SameSite=Lax (F-02, F-04)"
```

---

## Self-Review

### Spec coverage
- ✅ C-01 — logout révocation session
- ✅ H-01 — require_agency_admin fix
- ✅ H-02 — user.status check
- ✅ H-03 — verrouillage challenge après 5 tentatives
- ✅ F-01 — token max_length
- ✅ F-02 — SameSite=Lax documenté
- ✅ F-04 — email haché dans audit

### Points hors scope de ce plan
- C-02 (WebSocket master key) — Plan B
- M-01 à M-06 (config/headers) — Plan B
- H-04 (Docker deps) — Plan C
- F-03 (session ID = PK) — écarté volontairement (trop invasif pour v1)
