"""List non-secret platform connection records after Console authorization."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.application.ports import OrganizationAuthorizer, PlatformConnectionReader
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)
from muxivo_console.domain.connections import PlatformConnection


@dataclass(frozen=True, slots=True)
class PlatformConnectionPage:
    items: tuple[PlatformConnection, ...]
    next_cursor: UUID | None


@dataclass(slots=True)
class ListPlatformConnections:
    authorizer: OrganizationAuthorizer
    connections: PlatformConnectionReader

    async def execute(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        after_id: UUID | None = None,
        limit: int = 50,
    ) -> PlatformConnectionPage:
        if not 1 <= limit <= 100:
            raise ValueError("Connection list limit must be between 1 and 100.")
        decision = await self.authorizer.authorize(
            AuthorizationRequest(
                actor_id=actor_id,
                organization_id=organization_id,
                resource=AuthorizationResource.PLATFORM_CONNECTIONS,
                action=AuthorizationAction.READ,
            )
        )
        if not decision.allowed:
            raise AccessDeniedError("The actor is not allowed to view platform connections.")
        results = tuple(
            await self.connections.list_for_organization(
                organization_id=organization_id, after_id=after_id, limit=limit + 1
            )
        )
        has_next_page = len(results) > limit
        items = results[:limit]
        return PlatformConnectionPage(
            items=items,
            next_cursor=items[-1].id if has_next_page and items else None,
        )
