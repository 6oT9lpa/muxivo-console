from pydantic import BaseModel

from muxivo_console.domain.activity import Platform


class PlatformServerStatisticsResponse(BaseModel):
    organization_id: str
    connection_id: str
    platform: Platform
    period_days: int
    total_messages: int
    active_users: int
    active_channels: int
    current_member_count: int
    total_voice_minutes: int
    joins: int
    leaves: int
    net_member_growth: int
    moderation_events: int
