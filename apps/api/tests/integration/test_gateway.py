"""Tests d'intégration — gateway."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def test_gateway_requires_session(client):
    """Le gateway refuse les requêtes sans session."""
    res = client.get("/gateway/env_123/")
    assert res.status_code == 401


def test_gateway_unknown_env(client):
    """TODO: tester avec une session valide et un env inexistant → 404."""
    pass  # Nécessite une DB de test configurée
