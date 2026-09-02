"""Command for completing password recovery."""

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CompletePasswordRecoveryCommand:
    """Carry a one-time recovery token without exposing secrets in repr output."""

    token: str = field(repr=False)
    new_password: str = field(repr=False)
    correlation_id: UUID
