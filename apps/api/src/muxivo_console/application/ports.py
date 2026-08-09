from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from muxivo_console.domain.activity import ControlModule
from muxivo_console.domain.authorization import AuthorizationDecision, AuthorizationRequest
from muxivo_console.domain.organizations import OrganizationMembership


class ModuleCatalog(Protocol):
    """Outbound port implemented by a platform Control API adapter."""

    async def list_for_organization(
        self, *, organization_id: UUID, actor_id: UUID
    ) -> Sequence[ControlModule]: ...


class OrganizationAuthorizer(Protocol):
    """Inbound policy port, evaluated before every Console use case."""

    async def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision: ...


class OrganizationMembershipReader(Protocol):
    """Outbound port for the Console-owned organization membership store."""

    async def get_membership(
        self, *, actor_id: UUID, organization_id: UUID
    ) -> OrganizationMembership | None: ...
