from datetime import datetime

from pydantic import BaseModel, Field


class AuditEventResponse(BaseModel):
    id: str
    correlation_id: str
    actor_id: str | None
    action: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    resource_id: str | None
    result: str = Field(min_length=1)
    created_at: datetime


class AuditEventListResponse(BaseModel):
    items: list[AuditEventResponse]
    next_cursor: str | None
