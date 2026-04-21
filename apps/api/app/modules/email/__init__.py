from app.config import settings
from app.modules.email.provider import (
    EmailProvider,
    FakeEmailProvider,
    SmtpEmailProvider,
)

_default_provider: EmailProvider | None = None


def _build_provider() -> EmailProvider:
    """Sélectionne le provider selon settings.EMAIL_PROVIDER.

    - ``fake``  : stocke en mémoire (tests, fallback)
    - ``smtp``  : envoi SMTP (dev avec Mailpit, ou serveur SMTP interne)
    - ``resend``: Plan 5 hardening (non implémenté)
    """
    kind = settings.EMAIL_PROVIDER.lower()
    if kind == "smtp":
        return SmtpEmailProvider(
            host=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            from_addr=settings.SMTP_FROM,
            user=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
        )
    # Default / "fake" / "resend" (pas encore implémenté)
    return FakeEmailProvider()


def get_email_provider() -> EmailProvider:
    global _default_provider
    if _default_provider is None:
        _default_provider = _build_provider()
    return _default_provider


def override_email_provider(provider: EmailProvider) -> None:
    """Pour les tests — force un provider spécifique."""
    global _default_provider
    _default_provider = provider
