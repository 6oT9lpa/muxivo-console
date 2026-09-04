"""Command for resending a pending e-mail verification code."""

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ResendEmailPasswordRegistrationCommand:
    """Carry only the pending-flow bearer token at the application boundary."""

    token: str = field(repr=False)
    correlation_id: UUID
