from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from muxivo_console.domain.activity import Platform
from muxivo_console.domain.connections import ConnectionStatus


class PlatformConnectionCreateRequest(BaseModel):
    platform: Platform
    external_resource_id: str = Field(min_length=1, max_length=255)

    @field_validator("external_resource_id")
    @classmethod
    def require_non_blank_external_resource_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("External resource ID must not be blank.")
        return normalized


class PlatformConnectionResponse(BaseModel):
    id: UUID
    organization_id: UUID
    platform: Platform
    external_resource_id: str
    status: ConnectionStatus


class PlatformConnectionListResponse(BaseModel):
    items: list[PlatformConnectionResponse]
    next_cursor: UUID | None = None
