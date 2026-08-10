"""HTTP boundary for a tenant's secret-free Console audit timeline."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status

from muxivo_console.application.list_audit_events import ListAuditEvents
from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.contracts.v1.audit_events import AuditEventListResponse, AuditEventResponse

AuditResultFilter = Literal["allowed", "denied", "succeeded", "failed"]


def create_audit_event_router(list_audit_events: ListAuditEvents) -> APIRouter:
    router = APIRouter(prefix="/api/v1/organizations", tags=["audit-events"])

    @router.get("/{organization_id}/audit-events", response_model=AuditEventListResponse)
    async def list_organization_audit_events(
        organization_id: UUID,
        request: Request,
        cursor: UUID | None = None,
        actor_id: UUID | None = None,
        action: str | None = Query(default=None, min_length=1, max_length=128),
        resource_type: str | None = Query(default=None, min_length=1, max_length=128),
        result: AuditResultFilter | None = None,
        limit: int = Query(default=50, ge=1, le=100),
    ) -> AuditEventListResponse:
        authenticated_actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(authenticated_actor_id, UUID):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        try:
            page = await list_audit_events.execute(
                actor_id=authenticated_actor_id,
                organization_id=organization_id,
                after_event_id=cursor,
                filter_actor_id=actor_id,
                action=action,
                resource_type=resource_type,
                result=result,
                limit=limit,
            )
        except AccessDeniedError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization audit access denied",
            ) from exc
        return AuditEventListResponse(
            items=[
                AuditEventResponse(
                    id=entry.id,
                    correlation_id=entry.correlation_id,
                    actor_id=entry.actor_id,
                    organization_id=entry.organization_id,
                    action=entry.action,
                    resource_type=entry.resource_type,
                    resource_id=entry.resource_id,
                    result=entry.result,
                    created_at=entry.created_at,
                )
                for entry in page.items
            ],
            next_cursor=page.next_cursor,
        )

    return router
