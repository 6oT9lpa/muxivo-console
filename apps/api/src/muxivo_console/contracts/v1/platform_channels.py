from pydantic import BaseModel

from muxivo_console.domain.activity import Platform
from muxivo_console.domain.channels import ChannelKind


class PlatformChannelResponse(BaseModel):
    id: str
    name: str
    kind: ChannelKind


class PlatformChannelCatalogResponse(BaseModel):
    organization_id: str
    connection_id: str
    platform: Platform
    items: list[PlatformChannelResponse]
