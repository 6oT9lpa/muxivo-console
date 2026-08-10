"""HTTP boundary for tenant discovery in the first-party Console session."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status

from muxivo_console.application.list_organizations import ListOrganizations
from muxivo_console.contracts.v1.organizations import (
    OrganizationAccessResponse,
    OrganizationListResponse,
)


def create_organization_query_router(list_organizations: ListOrganizations) -> APIRouter:
    router = APIRouter(prefix="/api/v1/organizations", tags=["organizations"])

    @router.get("", response_model=OrganizationListResponse)
    async def list_actor_organizations(
        request: Request,
        cursor: UUID | None = None,
        limit: int = Query(default=50, ge=1, le=100),
    ) -> OrganizationListResponse:
        actor_id = getattr(request.state, "actor_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        page = await list_organizations.execute(
            actor_id=actor_id,
            after_organization_id=cursor,
            limit=limit,
        )
        return OrganizationListResponse(
            items=[
                OrganizationAccessResponse(
                    id=access.organization.id,
                    name=access.organization.name,
                    slug=access.organization.slug,
                    role=access.role,
                )
                for access in page.items
            ],
            next_cursor=page.next_cursor,
        )

    return router
