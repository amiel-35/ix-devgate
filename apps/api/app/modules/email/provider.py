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
