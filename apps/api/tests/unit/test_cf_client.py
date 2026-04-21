"""Tests unitaires — CFClient (respx mock)."""
import respx
import httpx
import pytest

from app.modules.cloudflare.client import CFClient, CFTunnel, CFAccessApp, CFServiceToken


FAKE_TOKEN = "test-cf-token"
FAKE_ACCOUNT = "acc-123"
FAKE_ZONE = "zone-456"
BASE = "https://api.cloudflare.com/client/v4"


def make_client() -> CFClient:
    return CFClient(api_token=FAKE_TOKEN, account_id=FAKE_ACCOUNT, zone_id=FAKE_ZONE)


@respx.mock
def test_list_tunnels_returns_devgate_tunnels():
    respx.get(f"{BASE}/accounts/{FAKE_ACCOUNT}/cfd_tunnel").mock(
        return_value=httpx.Response(200, json={
            "result": [
                {"id": "t-1", "name": "devgate-acme", "status": "active", "connections": []},
                {"id": "t-2", "name": "other-tunnel", "status": "active", "connections": []},
            ],
            "success": True,
        })
    )
    client = make_client()
    tunnels = client.list_tunnels()
    # Only devgate-* tunnels are returned
    assert len(tunnels) == 1
    assert tunnels[0].id == "t-1"
    assert tunnels[0].name == "devgate-acme"


@respx.mock
def test_create_access_app_returns_app():
    respx.post(f"{BASE}/accounts/{FAKE_ACCOUNT}/access/apps").mock(
        return_value=httpx.Response(200, json={
            "result": {"id": "app-1", "name": "devgate-test", "domain": "test.example.com"},
            "success": True,
        })
    )
    client = make_client()
    app = client.create_access_app("devgate-test", "test.example.com")
    assert app.id == "app-1"
    assert isinstance(app, CFAccessApp)


@respx.mock
def test_create_service_token_returns_token_with_secret():
    respx.post(f"{BASE}/accounts/{FAKE_ACCOUNT}/access/service_tokens").mock(
        return_value=httpx.Response(200, json={
            "result": {
                "id": "tok-1",
                "client_id": "client-abc",
                "client_secret": "secret-xyz",
            },
            "success": True,
        })
    )
    client = make_client()
    token = client.create_service_token("devgate-test")
    assert token.id == "tok-1"
    assert token.client_secret == "secret-xyz"
    assert isinstance(token, CFServiceToken)


@respx.mock
def test_create_dns_cname_returns_record_id():
    respx.post(f"{BASE}/zones/{FAKE_ZONE}/dns_records").mock(
        return_value=httpx.Response(200, json={
            "result": {"id": "dns-1", "name": "test.example.com", "type": "CNAME"},
            "success": True,
        })
    )
    client = make_client()
    record_id = client.create_dns_cname("test.example.com", "tunnel-id-abc")
    assert record_id == "dns-1"
