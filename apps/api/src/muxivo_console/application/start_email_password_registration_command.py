"""Command for starting an e-mail verification registration."""

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class StartEmailPasswordRegistrationCommand:
    """Carry registration input without putting the password in logs or repr."""

    email: str
    password: str = field(repr=False)
    display_name: str
    correlation_id: UUID
