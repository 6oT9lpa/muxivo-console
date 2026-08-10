from pydantic import BaseModel

from muxivo_console.domain.activity import Platform
from muxivo_console.domain.platforms import PlatformAdapterCapability


class PlatformAdapterResponse(BaseModel):
    platform: Platform
    capabilities: list[PlatformAdapterCapability]


class PlatformAdapterListResponse(BaseModel):
    items: list[PlatformAdapterResponse]
