from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from muxivo_console.domain.activity import Platform
from muxivo_console.domain.connection_status_reason import ConnectionStatusReason
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


class PlatformConnectionGrantedScopeResponse(BaseModel):
    key: str
    display_name: str
    description: str
    status: Literal["pending", "granted", "requires_reauthorization", "revoked"]


class PlatformConnectionResponse(BaseModel):
    id: UUID
    organization_id: UUID
    platform: Platform
    external_resource_id: str
    status: ConnectionStatus
    status_reason: ConnectionStatusReason | None = None
    granted_scopes: list[PlatformConnectionGrantedScopeResponse] = Field(default_factory=list)


class PlatformConnectionListResponse(BaseModel):
    items: list[PlatformConnectionResponse]
    next_cursor: UUID | None = None


class PlatformConnectionCandidateResponse(BaseModel):
    """A selectable platform resource; credentials never belong in this contract."""

    platform: Platform
    external_resource_id: str = Field(min_length=1, max_length=255)
    display_name: str = Field(min_length=1, max_length=255)


class PlatformConnectionCandidateListResponse(BaseModel):
    platform: Platform
    identity_linked: bool
    items: list[PlatformConnectionCandidateResponse] = Field(default_factory=list)
