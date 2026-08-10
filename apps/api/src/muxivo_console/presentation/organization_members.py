"""HTTP boundary for Console-owned organization membership discovery."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status

from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.application.list_organization_members import ListOrganizationMembers
from muxivo_console.contracts.v1.organization_members import (
    OrganizationMemberListResponse,
    OrganizationMemberResponse,
)


def create_organization_member_router(list_members: ListOrganizationMembers) -> APIRouter:
    router = APIRouter(prefix="/api/v1/organizations", tags=["organization-memberships"])

    @router.get("/{organization_id}/members", response_model=OrganizationMemberListResponse)
    async def list_organization_members(
        organization_id: UUID,
        request: Request,
        cursor: UUID | None = None,
        limit: int = Query(default=50, ge=1, le=100),
    ) -> OrganizationMemberListResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        try:
            page = await list_members.execute(
                actor_id=actor_id,
                organization_id=organization_id,
                after_membership_id=cursor,
                limit=limit,
            )
        except AccessDeniedError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization member access denied",
            ) from exc
        return OrganizationMemberListResponse(
            items=[
                OrganizationMemberResponse(
                    membership_id=member.membership_id,
                    user_id=member.user_id,
                    display_name=member.display_name,
                    role=member.role,
                )
                for member in page.items
            ],
            next_cursor=page.next_cursor,
        )

    return router
