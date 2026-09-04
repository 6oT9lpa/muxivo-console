"""Command for persisting a registration after inbox ownership is verified."""

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CompleteEmailPasswordRegistrationCommand:
    """Carry encrypted-flow output without exposing the password hash in repr."""

    normalized_email: str
    display_name: str
    password_hash: str = field(repr=False)
    correlation_id: UUID
