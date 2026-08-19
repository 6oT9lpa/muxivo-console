from pydantic import BaseModel

from muxivo_console.domain.activity import Platform


class PlatformAuditTimelineEventResponse(BaseModel):
    event_type: str
    occurred_at: str


class PlatformAuditTimelineResponse(BaseModel):
    organization_id: str
    connection_id: str
    platform: Platform
    items: list[PlatformAuditTimelineEventResponse]
    limit: int
