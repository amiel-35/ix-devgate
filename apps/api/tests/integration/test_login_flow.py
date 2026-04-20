"""Tests d'intégration — flow login complet : start → verify → session."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

# TODO: configurer une DB de test en mémoire (SQLite) pour les tests d'intégration
# Pour l'instant, ces tests documentent le comportement attendu

@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def test_login_start_unknown_email(client):
    """Un email inconnu renvoie ok=True (évite l'énumération)."""
    res = client.post("/auth/start", json={"email": "unknown@example.com"})
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True


def test_login_verify_invalid_token(client):
    """Un token invalide renvoie 404."""
    res = client.post("/auth/verify", json={"token": "invalid-token"})
    assert res.status_code in (404, 410)


def test_portal_requires_session(client):
    """Le portail est inaccessible sans session."""
    res = client.get("/me/environments")
    assert res.status_code == 401


def test_admin_requires_agency_role(client):
    """Le back-office est inaccessible sans session agency_admin."""
    res = client.get("/admin/organizations")
    assert res.status_code == 401
