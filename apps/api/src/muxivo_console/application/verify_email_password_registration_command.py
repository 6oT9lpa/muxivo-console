"""Command for consuming a pending e-mail verification code."""

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class VerifyEmailPasswordRegistrationCommand:
    """Carry a bearer token and six-digit code without exposing either in repr."""

    token: str = field(repr=False)
    code: str = field(repr=False)
    correlation_id: UUID
