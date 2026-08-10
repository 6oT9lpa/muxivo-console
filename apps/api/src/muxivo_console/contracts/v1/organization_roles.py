from uuid import UUID

from pydantic import BaseModel

from muxivo_console.domain.organizations import OrganizationRole


class OrganizationMemberRoleUpdateRequest(BaseModel):
    role: OrganizationRole


class OrganizationMemberRoleResponse(BaseModel):
    membership_id: UUID
    user_id: UUID
    display_name: str
    role: OrganizationRole
