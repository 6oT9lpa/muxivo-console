from pydantic import BaseModel

from muxivo_console.domain.activity import Platform


class PlatformDashboardSummaryResponse(BaseModel):
    organization_id: str
    connection_id: str
    platform: Platform
    messages_today: int
    ai_flagged_today: int
    creator_sources: int
    bot_latency_ms: int | None
