"""Development-only static module catalog adapter."""

from collections.abc import Sequence
from uuid import UUID

from muxivo_console.domain.activity import (
    ControlModule,
    ModuleCapability,
    ModuleStatus,
    Platform,
)


class StaticModuleCatalog:
    """Provide a local boundary smoke catalog without accessing Discord data."""

    async def list_for_organization(
        self, *, organization_id: UUID, actor_id: UUID, correlation_id: UUID
    ) -> Sequence[ControlModule]:
        return (
            ControlModule(
                key="discord.dashboard",
                display_name="Discord dashboard",
                platform=Platform.DISCORD,
                capability=ModuleCapability.VIEW,
                status=ModuleStatus.AVAILABLE,
            ),
        )
