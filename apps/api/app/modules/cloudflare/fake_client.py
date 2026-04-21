"""FakeCFClient — implémentation en mémoire du CFClient pour les tests."""
from dataclasses import dataclass, field

from app.modules.cloudflare.client import CFAccessApp, CFServiceToken, CFTunnel


class FakeCFError(Exception):
    """Simule une erreur CF API dans les tests."""


class FakeCFClient:
    """Client CF en mémoire pour les tests d'intégration.

    Usage :
        fake = FakeCFClient()
        fake.tunnels = [CFTunnel(id="t-1", name="devgate-acme", status="active")]
        fake.fail_at = "create_service_token"  # Simule une erreur sur cette étape
    """

    def __init__(self) -> None:
        self.fail_at: str | None = None
        self.tunnels: list[CFTunnel] = [
            CFTunnel(id="tunnel-fake-1", name="devgate-test", status="active"),
        ]
        # Enregistrements des appels effectués
        self.created_apps: list[dict] = []
        self.created_policies: list[dict] = []
        self.created_tokens: list[dict] = []
        self.created_dns: list[dict] = []
        self.deleted_apps: list[str] = []
        self.deleted_policies: list[tuple[str, str]] = []
        self.revoked_tokens: list[str] = []
        self.deleted_dns: list[str] = []

    def _maybe_fail(self, step: str) -> None:
        if self.fail_at == step:
            raise FakeCFError(f"Simulated CF API failure at {step}")

    def list_tunnels(self) -> list[CFTunnel]:
        self._maybe_fail("list_tunnels")
        return list(self.tunnels)

    def create_access_app(self, name: str, domain: str) -> CFAccessApp:
        self._maybe_fail("create_access_app")
        app_id = f"app-fake-{len(self.created_apps) + 1}"
        self.created_apps.append({"id": app_id, "name": name, "domain": domain})
        return CFAccessApp(id=app_id, name=name, domain=domain)

    def delete_access_app(self, app_id: str) -> None:
        self._maybe_fail("delete_access_app")
        self.deleted_apps.append(app_id)

    def create_policy(self, app_id: str, name: str) -> str:
        self._maybe_fail("create_policy")
        policy_id = f"policy-fake-{len(self.created_policies) + 1}"
        self.created_policies.append({"id": policy_id, "app_id": app_id, "name": name})
        return policy_id

    def delete_policy(self, app_id: str, policy_id: str) -> None:
        self._maybe_fail("delete_policy")
        self.deleted_policies.append((app_id, policy_id))

    def create_service_token(self, name: str) -> CFServiceToken:
        self._maybe_fail("create_service_token")
        token_id = f"token-fake-{len(self.created_tokens) + 1}"
        token = CFServiceToken(
            id=token_id,
            client_id=f"client-id-{token_id}",
            client_secret=f"client-secret-{token_id}",
        )
        self.created_tokens.append({"id": token_id, "name": name})
        return token

    def revoke_service_token(self, token_id: str) -> None:
        self._maybe_fail("revoke_service_token")
        self.revoked_tokens.append(token_id)

    def create_dns_cname(self, name: str, tunnel_id: str) -> str:
        self._maybe_fail("create_dns_cname")
        record_id = f"dns-fake-{len(self.created_dns) + 1}"
        self.created_dns.append({"id": record_id, "name": name, "tunnel_id": tunnel_id})
        return record_id

    def delete_dns_record(self, record_id: str) -> None:
        self._maybe_fail("delete_dns_record")
        self.deleted_dns.append(record_id)
