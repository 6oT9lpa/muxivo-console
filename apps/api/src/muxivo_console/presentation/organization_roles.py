"""HTTP boundary for audited Console organization role changes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from muxivo_console.application.change_organization_member_role import (
    ChangeOrganizationMemberRole,
    ChangeOrganizationMemberRoleCommand,
    OrganizationMemberNotFoundError,
    OrganizationRoleChangeConflictError,
    OrganizationRoleChangeRejectedError,
)
from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.contracts.v1.organization_roles import (
    OrganizationMemberRoleResponse,
    OrganizationMemberRoleUpdateRequest,
)


def create_organization_role_router(change_role: ChangeOrganizationMemberRole) -> APIRouter:
    router = APIRouter(prefix="/api/v1/organizations", tags=["organization-memberships"])

    @router.patch(
        "/{organization_id}/members/{membership_id}/role",
        response_model=OrganizationMemberRoleResponse,
    )
    async def update_organization_member_role(
        organization_id: UUID,
        membership_id: UUID,
        payload: OrganizationMemberRoleUpdateRequest,
        request: Request,
    ) -> OrganizationMemberRoleResponse:
        actor_id = getattr(request.state, "actor_id", None)
        correlation_id = getattr(request.state, "correlation_id", None)
        if not isinstance(actor_id, UUID):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        if not isinstance(correlation_id, UUID):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Role management is unavailable",
            )
        try:
            member = await change_role.execute(
                ChangeOrganizationMemberRoleCommand(
                    actor_id=actor_id,
                    organization_id=organization_id,
                    membership_id=membership_id,
                    role=payload.role,
                    correlation_id=correlation_id,
                )
            )
        except (AccessDeniedError, OrganizationRoleChangeRejectedError) as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization role change denied",
            ) from exc
        except OrganizationMemberNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization member not found",
            ) from exc
        except OrganizationRoleChangeConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Organization membership changed; reload and retry",
            ) from exc
        return OrganizationMemberRoleResponse(
            membership_id=member.membership_id,
            user_id=member.user_id,
            display_name=member.display_name,
            role=member.role,
        )

    return router
