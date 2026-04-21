from __future__ import annotations

import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage
from typing import Any


class EmailProvider(ABC):
    @abstractmethod
    def send_magic_link(self, to: str, link: str) -> None: ...

    @abstractmethod
    def send_otp(self, to: str, code: str) -> None: ...


class FakeEmailProvider(EmailProvider):
    """Capture les envois en mémoire. Utilisé en tests."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def send_magic_link(self, to: str, link: str) -> None:
        self.sent.append({"kind": "magic_link", "to": to, "link": link})

    def send_otp(self, to: str, code: str) -> None:
        self.sent.append({"kind": "otp", "to": to, "code": code})

    def clear(self) -> None:
        self.sent = []


class SmtpEmailProvider(EmailProvider):
    """Provider SMTP — utilisé en dev avec Mailpit (host=mailpit:1025)
    ou avec un serveur SMTP authentifié (Brevo, Mailgun, Amazon SES…).

    Si SMTP_USER et SMTP_PASSWORD sont définis, STARTTLS + login sont activés.
    Mailpit en dev ne nécessite pas d'auth — laisser user/password vides.
    """

    def __init__(
        self,
        host: str,
        port: int,
        from_addr: str,
        user: str = "",
        password: str = "",
    ) -> None:
        self.host = host
        self.port = port
        self.from_addr = from_addr
        self.user = user
        self.password = password

    def _send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = to
        msg.set_content(body)
        with smtplib.SMTP(self.host, self.port, timeout=10) as s:
            if self.user and self.password:
                s.starttls()
                s.login(self.user, self.password)
            s.send_message(msg)

    def send_magic_link(self, to: str, link: str) -> None:
        body = (
            "Bonjour,\n\n"
            "Voici votre lien de connexion sécurisé à DevGate :\n\n"
            f"{link}\n\n"
            "Ce lien expire dans 15 minutes et ne peut être utilisé qu'une seule fois.\n\n"
            "Si vous n'avez pas demandé cette connexion, ignorez cet email.\n\n"
            "— DevGate"
        )
        self._send(to, "Votre lien de connexion DevGate", body)

    def send_otp(self, to: str, code: str) -> None:
        body = (
            "Bonjour,\n\n"
            "Votre code à usage unique DevGate :\n\n"
            f"    {code}\n\n"
            "Ce code est valable pendant 10 minutes.\n\n"
            "Si vous n'avez pas demandé ce code, ignorez cet email.\n\n"
            "— DevGate"
        )
        self._send(to, "Votre code DevGate", body)
