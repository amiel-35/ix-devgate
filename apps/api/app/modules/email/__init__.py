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
