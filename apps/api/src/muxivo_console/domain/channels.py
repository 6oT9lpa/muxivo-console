"""Platform-neutral channel resources that may be selected by Console features."""

from dataclasses import dataclass
from enum import StrEnum

from muxivo_console.domain.activity import Platform


class ChannelKind(StrEnum):
    TEXT = "text"
    VOICE = "voice"
    ANNOUNCEMENT = "announcement"


@dataclass(frozen=True, slots=True)
class PlatformChannel:
    id: str
    name: str
    kind: ChannelKind

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.name.strip():
            raise ValueError("Channel identifier and name must be non-empty.")


@dataclass(frozen=True, slots=True)
class PlatformChannelCatalog:
    platform: Platform
    items: tuple[PlatformChannel, ...]
