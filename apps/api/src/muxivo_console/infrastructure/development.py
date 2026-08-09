"""Explicitly development-only adapters used until auth and Control APIs are wired."""

from collections.abc import Sequence
from uuid import UUID

from muxivo_console.domain.activity import (
    ControlModule,
    ModuleCapability,
    ModuleStatus,
    Platform,
)
from muxivo_console.domain.authorization import AuthorizationDecision, AuthorizationRequest


class DenyByDefaultOrganizationAuthorizer:
    async def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        return AuthorizationDecision.deny()


class StaticModuleCatalog:
    """Temporary catalog proving the Console boundary; it never accesses Discord DB."""

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
