"""List a tenant's secret-free audit timeline after Console authorization."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.application.ports import OrganizationAuthorizer
from muxivo_console.domain.audit import AuditEntry
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)


class AuditEntryReader(Protocol):
    """Reads audit projections scoped to exactly one Console organization."""

    async def list_for_organization(
        self,
        *,
        organization_id: UUID,
        after_event_id: UUID | None,
        actor_id: UUID | None,
        action: str | None,
        resource_type: str | None,
        result: str | None,
        limit: int,
    ) -> Sequence[AuditEntry]: ...


@dataclass(frozen=True, slots=True)
class AuditEntryPage:
    items: tuple[AuditEntry, ...]
    next_cursor: UUID | None


@dataclass(slots=True)
class ListAuditEvents:
    authorizer: OrganizationAuthorizer
    audit_events: AuditEntryReader

    async def execute(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        after_event_id: UUID | None = None,
        filter_actor_id: UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        result: str | None = None,
        limit: int = 50,
    ) -> AuditEntryPage:
        if not 1 <= limit <= 100:
            raise ValueError("Audit event list limit must be between 1 and 100.")
        if result is not None and result not in {"allowed", "denied", "succeeded", "failed"}:
            raise ValueError("Unsupported audit result filter.")
        decision = await self.authorizer.authorize(
            AuthorizationRequest(
                actor_id=actor_id,
                organization_id=organization_id,
                resource=AuthorizationResource.AUDIT_EVENTS,
                action=AuthorizationAction.READ,
            )
        )
        if not decision.allowed:
            raise AccessDeniedError("The actor is not allowed to view organization audit events.")
        entries = tuple(
            await self.audit_events.list_for_organization(
                organization_id=organization_id,
                after_event_id=after_event_id,
                actor_id=filter_actor_id,
                action=action,
                resource_type=resource_type,
                result=result,
                limit=limit + 1,
            )
        )
        has_next_page = len(entries) > limit
        items = entries[:limit]
        return AuditEntryPage(
            items=items,
            next_cursor=items[-1].id if has_next_page and items else None,
        )
