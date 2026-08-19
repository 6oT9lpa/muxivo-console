from pydantic import BaseModel

from muxivo_console.domain.activity import Platform


class IntegrationSourceCountResponse(BaseModel):
    platform: str
    total: int
    active: int


class PlatformIntegrationsResponse(BaseModel):
    organization_id: str
    connection_id: str
    platform: Platform
    discord_bot_status: str
    creator_platforms_status: str
    creator_poll_interval_seconds: int
    creator_sources: list[IntegrationSourceCountResponse]
    muxivo_core_status: str
    database_status: str
