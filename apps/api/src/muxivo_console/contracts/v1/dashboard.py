from uuid import UUID

from pydantic import BaseModel, Field

from muxivo_console.domain.activity import Platform


class PlatformDashboardSummaryResponse(BaseModel):
    organization_id: UUID
    connection_id: UUID
    platform: Platform
    messages_today: int = Field(ge=0)
    ai_flagged_today: int = Field(ge=0)
    creator_sources: int = Field(ge=0)
    bot_latency_ms: int | None = Field(default=None, ge=0)
