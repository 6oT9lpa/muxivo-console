from pydantic import BaseModel, Field

from muxivo_console.domain.activity import Platform


class PlatformAiModerationSummaryResponse(BaseModel):
    organization_id: str
    connection_id: str
    platform: Platform
    enforcement_mode: str = Field(min_length=1)
    test_mode: bool
    is_default_policy: bool
    covered_channel_count: int = Field(ge=0)
    log_channel_configured: bool
    label_count: int = Field(ge=0)
    blacklist_word_count: int = Field(ge=0)
    allowed_domain_count: int = Field(ge=0)
    automated_timeout_enabled: bool
    automated_kick_enabled: bool
    automated_ban_enabled: bool
