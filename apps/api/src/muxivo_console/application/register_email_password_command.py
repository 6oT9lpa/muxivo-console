"""Command for first-party e-mail/password registration."""

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RegisterEmailPasswordCommand:
    """Carry registration input without exposing the password in repr output."""

    email: str
    password: str = field(repr=False)
    display_name: str
    correlation_id: UUID
