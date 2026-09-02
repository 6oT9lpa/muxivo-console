from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from muxivo_console.domain.sessions import SessionAssuranceLevel


class BrowserSessionResponse(BaseModel):
    id: UUID
    is_current: bool
    assurance_level: SessionAssuranceLevel
    authenticated_at: datetime | None = None
    last_seen_at: datetime | None = None
    expires_at: datetime
    device_label: str
    ip_fingerprint: str | None = None
    user_agent_fingerprint: str | None = None


class BrowserSessionListResponse(BaseModel):
    items: list[BrowserSessionResponse] = Field(default_factory=list)


class BrowserSessionBulkRevocationResponse(BaseModel):
    revoked_count: int = Field(ge=0)
