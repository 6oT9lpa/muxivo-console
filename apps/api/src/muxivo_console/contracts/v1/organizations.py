from uuid import UUID

from pydantic import BaseModel, Field, field_validator

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


class OrganizationAccessResponse(OrganizationResponse):
    role: OrganizationRole


class OrganizationListResponse(BaseModel):
    items: list[OrganizationAccessResponse]
    next_cursor: UUID | None = None
