from uuid import UUID

from pydantic import BaseModel

from muxivo_console.domain.activity import Platform


class ServerStatsSummaryResponse(BaseModel):
    total_messages: int
    active_users: int
    active_channels: int
    daily_active_users: int
    weekly_active_users: int
    monthly_active_users: int
    messages_per_active_user: float
    voice_users: int
    total_voice_minutes: int
    joins: int
    leaves: int
    joins_24h: int
    joins_7d: int
    joins_30d: int
    leaves_24h: int
    leaves_7d: int
    leaves_30d: int
    net_member_growth: int
    current_member_count: int
    moderation_events: int
    membership_history_since: str | None
    membership_history_complete: bool
    period_days: int


class ServerChannelStatsResponse(BaseModel):
    channel_id: str
    channel_name: str
    messages: int


class ServerHourlyStatsResponse(BaseModel):
    hour: int
    count: int


class ServerDailyStatsResponse(BaseModel):
    date: str
    count: int


class PlatformServerStatsResponse(BaseModel):
    organization_id: UUID
    connection_id: UUID
    platform: Platform
    summary: ServerStatsSummaryResponse
    channels: list[ServerChannelStatsResponse]
    hourly: list[ServerHourlyStatsResponse]
    daily: list[ServerDailyStatsResponse]
