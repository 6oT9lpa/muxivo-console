"""Command for beginning an external identity link."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.domain.identity import LoginIdentityProvider


@dataclass(frozen=True, slots=True)
class BeginIdentityLinkCommand:
    """Identify the active Console user and provider to link."""

    actor_id: UUID
    provider: LoginIdentityProvider
    correlation_id: UUID
