"""Command for platform connection candidate discovery."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.domain.activity import Platform


@dataclass(frozen=True, slots=True)
class ListPlatformConnectionCandidatesCommand:
    """Facts supplied by the HTTP boundary for one discovery request."""

    actor_id: UUID
    organization_id: UUID
    platform: Platform
    correlation_id: UUID
