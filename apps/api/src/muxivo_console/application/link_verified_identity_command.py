"""Command for linking a provider subject already verified by an adapter."""

from dataclasses import dataclass, field
from uuid import UUID

from muxivo_console.domain.identity import LoginIdentityProvider


@dataclass(frozen=True, slots=True)
class LinkVerifiedIdentityCommand:
    """Carry the verified subject without exposing it through repr/logging."""

    actor_id: UUID
    provider: LoginIdentityProvider
    verified_provider_subject: str = field(repr=False)
    correlation_id: UUID
