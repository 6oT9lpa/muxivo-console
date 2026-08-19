"""Secret-free, platform-neutral integration operational facts."""

from dataclasses import dataclass

from muxivo_console.domain.activity import Platform


@dataclass(frozen=True, slots=True)
class IntegrationSourceCount:
    platform: str
    total: int
    active: int

    def __post_init__(self) -> None:
        if (
            not self.platform.strip()
            or self.total < 0
            or self.active < 0
            or self.active > self.total
        ):
            raise ValueError("Integration source counts are invalid.")


@dataclass(frozen=True, slots=True)
class PlatformIntegrations:
    platform: Platform
    discord_bot_status: str
    creator_platforms_status: str
    creator_poll_interval_seconds: int
    creator_sources: tuple[IntegrationSourceCount, ...]
    muxivo_core_status: str
    database_status: str

    def __post_init__(self) -> None:
        if self.creator_poll_interval_seconds < 1:
            raise ValueError("Creator poll interval must be positive.")
        if not all(
            value.strip()
            for value in (
                self.discord_bot_status,
                self.creator_platforms_status,
                self.muxivo_core_status,
                self.database_status,
            )
        ):
            raise ValueError("Integration statuses must not be blank.")
