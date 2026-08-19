from pydantic import BaseModel

from muxivo_console.domain.activity import Platform


class PlatformBotSettingsResponse(BaseModel):
    organization_id: str
    connection_id: str
    platform: Platform
    subscription_tier: str
    activity_rotation_enabled: bool
    activity_rotation_interval_seconds: int
    retention_days: dict[str, int]
