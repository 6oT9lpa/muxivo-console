"""Command for first-party e-mail/password authentication."""

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AuthenticateEmailPasswordCommand:
    """Carry authentication input without exposing secrets in diagnostics."""

    email: str
    password: str = field(repr=False)
    correlation_id: UUID
    client_ip: str | None = field(default=None, repr=False)
    user_agent: str | None = field(default=None, repr=False)
