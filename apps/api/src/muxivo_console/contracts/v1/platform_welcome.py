from pydantic import BaseModel

from muxivo_console.domain.activity import Platform


class PlatformWelcomeSettingsResponse(BaseModel):
    organization_id: str
    connection_id: str
    platform: Platform
    title: str
    description: str
    thumbnail_url: str | None
    footer_text: str | None
    footer_icon_url: str | None
    color: int
    is_enabled: bool
    rules_channel_id: str | None
    roles_channel_id: str | None
