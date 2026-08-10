"""List Console organizations reachable through the current actor's memberships."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.ports import OrganizationAccessReader
from muxivo_console.domain.organizations import OrganizationAccess


@dataclass(frozen=True, slots=True)
class OrganizationAccessPage:
    items: tuple[OrganizationAccess, ...]
    next_cursor: UUID | None


@dataclass(slots=True)
class ListOrganizations:
    organizations: OrganizationAccessReader

    async def execute(
        self,
        *,
        actor_id: UUID,
        after_organization_id: UUID | None = None,
        limit: int = 50,
    ) -> OrganizationAccessPage:
        if not 1 <= limit <= 100:
            raise ValueError("Organization list limit must be between 1 and 100.")
        results = tuple(
            await self.organizations.list_for_actor(
                actor_id=actor_id,
                after_organization_id=after_organization_id,
                limit=limit + 1,
            )
        )
        has_next_page = len(results) > limit
        items = results[:limit]
        return OrganizationAccessPage(
            items=items,
            next_cursor=(
                items[-1].organization.id if has_next_page and items else None
            ),
        )
