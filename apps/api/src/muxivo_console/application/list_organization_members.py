"""List Console-owned organization memberships after tenant authorization."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.application.ports import OrganizationAuthorizer
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)
from muxivo_console.domain.organizations import OrganizationMember


class OrganizationMemberReader(Protocol):
    """Reads non-secret membership projections for one Console tenant."""

    async def list_for_organization(
        self, *, organization_id: UUID, after_membership_id: UUID | None, limit: int
    ) -> Sequence[OrganizationMember]: ...


@dataclass(frozen=True, slots=True)
class OrganizationMemberPage:
    items: tuple[OrganizationMember, ...]
    next_cursor: UUID | None


@dataclass(slots=True)
class ListOrganizationMembers:
    authorizer: OrganizationAuthorizer
    members: OrganizationMemberReader

    async def execute(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        after_membership_id: UUID | None = None,
        limit: int = 50,
    ) -> OrganizationMemberPage:
        if not 1 <= limit <= 100:
            raise ValueError("Organization member list limit must be between 1 and 100.")
        decision = await self.authorizer.authorize(
            AuthorizationRequest(
                actor_id=actor_id,
                organization_id=organization_id,
                resource=AuthorizationResource.ORGANIZATION_MEMBERSHIPS,
                action=AuthorizationAction.READ,
            )
        )
        if not decision.allowed:
            raise AccessDeniedError("The actor is not allowed to view organization members.")
        results = tuple(
            await self.members.list_for_organization(
                organization_id=organization_id,
                after_membership_id=after_membership_id,
                limit=limit + 1,
            )
        )
        has_next_page = len(results) > limit
        items = results[:limit]
        return OrganizationMemberPage(
            items=items,
            next_cursor=items[-1].membership_id if has_next_page and items else None,
        )
