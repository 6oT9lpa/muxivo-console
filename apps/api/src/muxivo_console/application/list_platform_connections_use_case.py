"""List non-secret platform connection records after Console authorization."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.access_denied_error import AccessDeniedError
from muxivo_console.application.platform_connection_page import PlatformConnectionPage
from muxivo_console.application.ports import OrganizationAuthorizer, PlatformConnectionReader
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)

logger = logging.getLogger("muxivo_console.application.list_platform_connections")


@dataclass(slots=True)
class ListPlatformConnections:
    """Read paginated connection metadata without exposing platform credentials."""

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
        logger.info(
            "platform_connection.list.started",
            extra={
                "actor_id": str(actor_id),
                "organization_id": str(organization_id),
                "after_id": str(after_id) if after_id else None,
                "limit": limit,
            },
        )
        if not 1 <= limit <= 100:
            logger.warning(
                "platform_connection.list.invalid_limit",
                extra={
                    "actor_id": str(actor_id),
                    "organization_id": str(organization_id),
                    "limit": limit,
                },
            )
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
            logger.warning(
                "platform_connection.list.denied_rbac",
                extra={
                    "actor_id": str(actor_id),
                    "organization_id": str(organization_id),
                },
            )
            raise AccessDeniedError("The actor is not allowed to view platform connections.")
        results = tuple(
            await self.connections.list_for_organization(
                organization_id=organization_id, after_id=after_id, limit=limit + 1
            )
        )
        has_next_page = len(results) > limit
        items = results[:limit]
        page = PlatformConnectionPage(
            items=items,
            next_cursor=items[-1].id if has_next_page and items else None,
        )
        logger.info(
            "platform_connection.list.completed",
            extra={
                "actor_id": str(actor_id),
                "organization_id": str(organization_id),
                "item_count": len(page.items),
                "has_next_page": page.next_cursor is not None,
            },
        )
        return page
