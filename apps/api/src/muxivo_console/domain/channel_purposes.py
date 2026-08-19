"""Platform-neutral assignment of bot feature purposes to platform channels."""

from dataclasses import dataclass
from enum import StrEnum

from muxivo_console.domain.activity import Platform


class ChannelPurpose(StrEnum):
    WELCOME = "welcome"
    MEMBER_LOG = "member_log"
    MOD_LOG = "mod_log"
    MESSAGE_LOG = "message_log"
    CHANNEL_LOG = "channel_log"
    STREAM_ANNOUNCE = "stream_announce"
    DEV_BLOG = "dev_blog"
    AI_MODERATION_LOG = "ai_moderation_log"


@dataclass(frozen=True, slots=True)
class PlatformChannelPurposes:
    platform: Platform
    assignments: dict[ChannelPurpose, str]

    def __post_init__(self) -> None:
        if any(not channel_id.strip() for channel_id in self.assignments.values()):
            raise ValueError("Channel purpose assignments must have non-empty channel IDs.")
