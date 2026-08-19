"""Platform-neutral assignment of bot feature purposes to platform roles."""

from dataclasses import dataclass
from enum import StrEnum

from muxivo_console.domain.activity import Platform


class RolePurpose(StrEnum):
    ACTIVITY_ADMIN = "activity_admin"
    ACTIVITY_STREAMER = "activity_streamer"
    ACTIVITY_DEVELOPER = "activity_developer"
    PING_STREAM = "ping_stream"
    PING_DEV = "ping_dev"


@dataclass(frozen=True, slots=True)
class PlatformRolePurposes:
    platform: Platform
    assignments: dict[RolePurpose, str]

    def __post_init__(self) -> None:
        if any(not role_id.strip() for role_id in self.assignments.values()):
            raise ValueError("Role purpose assignments must have non-empty role IDs.")
