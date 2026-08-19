"""List organization audit facts after Console-owned authorization."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.application.ports import AuditEventReader, OrganizationAuthorizer
from muxivo_console.domain.audit import AuditLogEntry
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)


@dataclass(frozen=True, slots=True)
class AuditEventPage:
    items: tuple[AuditLogEntry, ...]
    next_cursor: UUID | None


@dataclass(slots=True)
class ListOrganizationAuditEvents:
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
        if not 1 <= limit <= 100:
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
            raise AccessDeniedError("The actor is not allowed to view organization audit events.")
        entries = tuple(
            await self.audit_events.list_for_organization(
                organization_id=organization_id, after_id=after_id, limit=limit + 1
            )
        )
        items = entries[:limit]
        return AuditEventPage(
            items=items,
            next_cursor=items[-1].id if len(entries) > limit and items else None,
        )
