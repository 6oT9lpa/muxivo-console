"""Command for registering a verified platform connection."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.domain.activity import Platform


@dataclass(frozen=True, slots=True)
class RegisterPlatformConnectionCommand:
    """Identify the owned platform resource to connect to an organization."""

    actor_id: UUID
    organization_id: UUID
    platform: Platform
    external_resource_id: str
    correlation_id: UUID
