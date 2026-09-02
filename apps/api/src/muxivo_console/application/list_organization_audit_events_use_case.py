"""List organization audit facts after Console-owned authorization."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.access_denied_error import AccessDeniedError
from muxivo_console.application.audit_event_page import AuditEventPage
from muxivo_console.application.ports import AuditEventReader, OrganizationAuthorizer
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)

logger = logging.getLogger("muxivo_console.application.list_organization_audit_events")


@dataclass(slots=True)
class ListOrganizationAuditEvents:
    """Read a bounded, cursor-paginated audit stream for an organization."""

    authorizer: OrganizationAuthorizer
    audit_events: AuditEventReader

    async def execute(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        after_id: UUID | None = None,
        limit: int = 50,
    ) -> AuditEventPage:
        logger.info(
            "organization.audit.list.started",
            extra={
                "actor_id": str(actor_id),
                "organization_id": str(organization_id),
                "after_id": str(after_id) if after_id else None,
                "limit": limit,
            },
        )
        if not 1 <= limit <= 100:
            logger.warning(
                "organization.audit.list.invalid_limit",
                extra={
                    "actor_id": str(actor_id),
                    "organization_id": str(organization_id),
                    "limit": limit,
                },
            )
            raise ValueError("Audit event page size must be between 1 and 100.")
        decision = await self.authorizer.authorize(
            AuthorizationRequest(
                actor_id,
                organization_id,
                AuthorizationResource.AUDIT_EVENTS,
                AuthorizationAction.READ,
            )
        )
        if not decision.allowed:
            logger.warning(
                "organization.audit.list.denied_rbac",
                extra={
                    "actor_id": str(actor_id),
                    "organization_id": str(organization_id),
                },
            )
            raise AccessDeniedError("The actor is not allowed to view organization audit events.")
        entries = tuple(
            await self.audit_events.list_for_organization(
                organization_id=organization_id, after_id=after_id, limit=limit + 1
            )
        )
        items = entries[:limit]
        page = AuditEventPage(
            items=items,
            next_cursor=items[-1].id if len(entries) > limit and items else None,
        )
        logger.info(
            "organization.audit.list.completed",
            extra={
                "actor_id": str(actor_id),
                "organization_id": str(organization_id),
                "item_count": len(page.items),
                "has_next_page": page.next_cursor is not None,
            },
        )
        return page
