"""The email seam. Deliberately unimplemented.

Nothing in this deployment can send email, and writing a fake sender that
silently discards messages would be worse than not having one: a password
reset that reports success and delivers nothing is the most damaging kind of
working-looking feature.

So the interface exists, the code that would use it is written against it, and
the only implementation says plainly that it cannot deliver. Recovery codes
(`sabi/accounts/recovery.py`) are what actually gets a student back into their
account today.

To make this real: implement `HttpMailer` against a provider's send endpoint
with `httpx`, which is already a dependency, and return it from `get_mailer()`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class MailUnavailable(RuntimeError):
    """Raised instead of pretending a message was sent."""


class Mailer(ABC):
    @abstractmethod
    def send(self, *, to: str, subject: str, body: str) -> None:
        """Deliver one message, or raise."""


class UnconfiguredMailer(Mailer):
    def send(self, *, to: str, subject: str, body: str) -> None:
        raise MailUnavailable(
            "this deployment has no email transport, so nothing can be sent; "
            "recovery codes are the way back into an account"
        )


def get_mailer() -> Mailer:
    return UnconfiguredMailer()


def can_send() -> bool:
    """Whether the interface can be relied on. Drives what the UI offers."""
    return not isinstance(get_mailer(), UnconfiguredMailer)
