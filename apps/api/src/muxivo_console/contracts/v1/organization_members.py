from uuid import UUID

from pydantic import BaseModel

from muxivo_console.domain.organizations import OrganizationRole


class OrganizationMemberResponse(BaseModel):
    membership_id: UUID
    user_id: UUID
    display_name: str
    role: OrganizationRole


class OrganizationMemberListResponse(BaseModel):
    items: list[OrganizationMemberResponse]
    next_cursor: UUID | None = None
