"""Platform-neutral, browser-safe welcome-message configuration."""

from dataclasses import dataclass

from muxivo_console.domain.activity import Platform


@dataclass(frozen=True, slots=True)
class PlatformWelcomeSettings:
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

    def __post_init__(self) -> None:
        if not self.title.strip() or not self.description.strip():
            raise ValueError("Welcome title and description must be non-empty.")
        if not 0 <= self.color <= 0xFFFFFF:
            raise ValueError("Welcome color must be a 24-bit RGB value.")
