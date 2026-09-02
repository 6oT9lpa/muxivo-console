"""Command for starting password recovery."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RequestPasswordRecoveryCommand:
    """Identify the account for a deliberately anti-enumeration recovery request."""

    email: str
    correlation_id: UUID
