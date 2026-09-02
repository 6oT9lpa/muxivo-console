from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from muxivo_console.domain.authorization import AuthorizationAction, AuthorizationResource
from muxivo_console.domain.organizations import OrganizationRole


class OrganizationCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128, examples=["Creator community"])

    @field_validator("name")
    @classmethod
    def require_non_blank_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Organization name must not be blank.")
        return normalized


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    slug: str


class OrganizationMembershipScopeRequest(BaseModel):
    resource: AuthorizationResource
    action: AuthorizationAction


class OrganizationMembershipScopeResponse(BaseModel):
    id: UUID | None = None
    resource: AuthorizationResource
    action: AuthorizationAction


class OrganizationMembershipResponse(BaseModel):
    id: UUID | None = None
    organization_id: UUID
    user_id: UUID
    role: OrganizationRole
    resource_scopes: list[OrganizationMembershipScopeResponse] = Field(default_factory=list)


class OrganizationListItemResponse(BaseModel):
    organization: OrganizationResponse
    membership: OrganizationMembershipResponse


class OrganizationListResponse(BaseModel):
    items: list[OrganizationListItemResponse] = Field(default_factory=list)


class OrganizationMemberCreateRequest(BaseModel):
    email: EmailStr
    role: OrganizationRole
    resource_scopes: list[OrganizationMembershipScopeRequest] = Field(default_factory=list)


class OrganizationMemberUpdateRequest(BaseModel):
    role: OrganizationRole
    resource_scopes: list[OrganizationMembershipScopeRequest] = Field(default_factory=list)


class OrganizationMemberListResponse(BaseModel):
    items: list[OrganizationMembershipResponse] = Field(default_factory=list)
