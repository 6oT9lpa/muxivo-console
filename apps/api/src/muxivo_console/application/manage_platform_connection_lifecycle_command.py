"""Command for a platform connection lifecycle operation."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.platform_connection_lifecycle_action import (
    PlatformConnectionLifecycleAction,
)


@dataclass(frozen=True, slots=True)
class ManagePlatformConnectionLifecycleCommand:
    """Identify the connection action and optional retry key."""

    actor_id: UUID
    organization_id: UUID
    connection_id: UUID
    action: PlatformConnectionLifecycleAction
    correlation_id: UUID
    idempotency_key: str | None = None
