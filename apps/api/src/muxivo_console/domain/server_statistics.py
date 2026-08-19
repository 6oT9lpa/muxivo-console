"""Aggregate platform-server statistics safe for browser display."""

from dataclasses import dataclass

from muxivo_console.domain.activity import Platform


@dataclass(frozen=True, slots=True)
class PlatformServerStatistics:
    """Counts only; member-level and message-level Activity data is excluded."""

    platform: Platform
    period_days: int
    total_messages: int
    active_users: int
    active_channels: int
    current_member_count: int
    total_voice_minutes: int
    joins: int
    leaves: int
    moderation_events: int

    def __post_init__(self) -> None:
        if self.period_days < 1 or any(
            value < 0
            for value in (
                self.total_messages,
                self.active_users,
                self.active_channels,
                self.current_member_count,
                self.total_voice_minutes,
                self.joins,
                self.leaves,
                self.moderation_events,
            )
        ):
            raise ValueError("Server statistics must contain non-negative aggregate counts.")
