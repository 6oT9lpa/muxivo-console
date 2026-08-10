from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

AuditResult = Literal["allowed", "denied", "succeeded", "failed"]


class AuditEventResponse(BaseModel):
    id: UUID
    correlation_id: UUID
    actor_id: UUID | None
    organization_id: UUID
    action: str
    resource_type: str
    resource_id: str | None
    result: AuditResult
    created_at: datetime


class AuditEventListResponse(BaseModel):
    items: list[AuditEventResponse]
    next_cursor: UUID | None = None
