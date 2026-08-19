from pydantic import BaseModel

from muxivo_console.domain.activity import Platform
from muxivo_console.domain.channel_purposes import ChannelPurpose


class ChannelPurposeAssignmentResponse(BaseModel):
    purpose: ChannelPurpose
    channel_id: str


class PlatformChannelPurposesResponse(BaseModel):
    organization_id: str
    connection_id: str
    platform: Platform
    items: list[ChannelPurposeAssignmentResponse]
