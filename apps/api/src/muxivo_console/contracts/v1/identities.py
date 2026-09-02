from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from muxivo_console.domain.identity import LoginIdentityProvider


class LoginIdentityResponse(BaseModel):
    id: UUID
    provider: LoginIdentityProvider
    linked_at: datetime
    last_used_at: datetime | None = None
    can_unlink: bool


class LoginIdentityListResponse(BaseModel):
    items: list[LoginIdentityResponse] = Field(default_factory=list)
