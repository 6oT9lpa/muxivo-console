"""Command for consuming an external identity link callback."""

from dataclasses import dataclass, field
from uuid import UUID

from muxivo_console.domain.identity import LoginIdentityProvider


@dataclass(frozen=True, slots=True)
class CompleteIdentityLinkCommand:
    """Carry callback values without exposing state or authorization code in repr."""

    provider: LoginIdentityProvider
    state: str = field(repr=False)
    authorization_code: str = field(repr=False)
    correlation_id: UUID
