from uuid import UUID

from pydantic import BaseModel, Field, field_validator


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
