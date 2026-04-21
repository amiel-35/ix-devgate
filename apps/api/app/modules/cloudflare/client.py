"""
Client Cloudflare API v4.

Utilise httpx synchrone (suffisant pour v1 monolithe).
Toutes les méthodes lèvent httpx.HTTPStatusError en cas d'erreur CF API.
"""
from dataclasses import dataclass, field

import httpx

CF_API_BASE = "https://api.cloudflare.com/client/v4"


@dataclass
class CFTunnel:
    id: str
    name: str
    status: str
    connections: list[dict] = field(default_factory=list)


@dataclass
class CFAccessApp:
    id: str
    name: str
    domain: str


@dataclass
class CFServiceToken:
    id: str
    client_id: str
    client_secret: str  # visible une seule fois à la création


class CFClient:
    """Wrapper httpx autour de l'API Cloudflare v4.

    api_token   : CF API token (scope : Tunnel read, Access write, DNS write)
    account_id  : ID du compte CF de l'agence
    zone_id     : Zone DNS pour les CNAME (CF_ZONE_ID)
    """

    def __init__(self, api_token: str, account_id: str, zone_id: str = "") -> None:
        self._account_id = account_id
        self._zone_id = zone_id
        self._headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, **params) -> dict:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(f"{CF_API_BASE}{path}", headers=self._headers, params=params)
            r.raise_for_status()
            return r.json()

    def _post(self, path: str, body: dict) -> dict:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(f"{CF_API_BASE}{path}", headers=self._headers, json=body)
            r.raise_for_status()
            return r.json()

    def _delete(self, path: str) -> None:
        with httpx.Client(timeout=15.0) as client:
            r = client.delete(f"{CF_API_BASE}{path}", headers=self._headers)
            r.raise_for_status()

    # ── Tunnels ───────────────────────────────────────────────────

    def list_tunnels(self) -> list[CFTunnel]:
        """Liste les tunnels actifs préfixés 'devgate-'."""
        data = self._get(
            f"/accounts/{self._account_id}/cfd_tunnel",
            is_deleted="false",
        )
        return [
            CFTunnel(
                id=t["id"],
                name=t["name"],
                status=t.get("status", "inactive"),
                connections=t.get("connections", []),
            )
            for t in data.get("result", [])
            if t["name"].startswith("devgate-")
        ]

    # ── Access apps ───────────────────────────────────────────────

    def create_access_app(self, name: str, domain: str) -> CFAccessApp:
        """Crée une Access application self-hosted sur le hostname donné."""
        data = self._post(
            f"/accounts/{self._account_id}/access/apps",
            {
                "name": name,
                "domain": domain,
                "type": "self_hosted",
                "session_duration": "24h",
            },
        )
        result = data["result"]
        return CFAccessApp(id=result["id"], name=result["name"], domain=result["domain"])

    def delete_access_app(self, app_id: str) -> None:
        self._delete(f"/accounts/{self._account_id}/access/apps/{app_id}")

    # ── Policies ──────────────────────────────────────────────────

    def create_policy(self, app_id: str, name: str) -> str:
        """Crée une policy 'allow any valid service token'. Retourne le policy_id."""
        data = self._post(
            f"/accounts/{self._account_id}/access/apps/{app_id}/policies",
            {
                "name": name,
                "decision": "non_identity",
                "include": [{"any_valid_service_token": {}}],
            },
        )
        return data["result"]["id"]

    def delete_policy(self, app_id: str, policy_id: str) -> None:
        self._delete(
            f"/accounts/{self._account_id}/access/apps/{app_id}/policies/{policy_id}"
        )

    # ── Service tokens ────────────────────────────────────────────

    def create_service_token(self, name: str) -> CFServiceToken:
        """Crée un service token. client_secret visible une seule fois."""
        data = self._post(
            f"/accounts/{self._account_id}/access/service_tokens",
            {"name": name},
        )
        result = data["result"]
        return CFServiceToken(
            id=result["id"],
            client_id=result["client_id"],
            client_secret=result["client_secret"],
        )

    def revoke_service_token(self, token_id: str) -> None:
        self._delete(f"/accounts/{self._account_id}/access/service_tokens/{token_id}")

    # ── DNS ───────────────────────────────────────────────────────

    def create_dns_cname(self, name: str, tunnel_id: str) -> str:
        """Crée un CNAME proxied vers {tunnel_id}.cfargotunnel.com. Retourne record_id."""
        data = self._post(
            f"/zones/{self._zone_id}/dns_records",
            {
                "type": "CNAME",
                "name": name,
                "content": f"{tunnel_id}.cfargotunnel.com",
                "proxied": True,
            },
        )
        return data["result"]["id"]

    def delete_dns_record(self, record_id: str) -> None:
        self._delete(f"/zones/{self._zone_id}/dns_records/{record_id}")
