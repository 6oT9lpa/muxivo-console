"""Platform-neutral read models for browser-ready server statistics."""

from dataclasses import dataclass

from muxivo_console.domain.activity import Platform


def _require_non_negative(value: int, field: str) -> None:
    if isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer.")


@dataclass(frozen=True, slots=True)
class ServerStatsSummary:
    total_messages: int
    active_users: int
    active_channels: int
    daily_active_users: int
    weekly_active_users: int
    monthly_active_users: int
    messages_per_active_user: float
    voice_users: int
    total_voice_minutes: int
    joins: int
    leaves: int
    joins_24h: int
    joins_7d: int
    joins_30d: int
    leaves_24h: int
    leaves_7d: int
    leaves_30d: int
    net_member_growth: int
    current_member_count: int
    moderation_events: int
    membership_history_since: str | None
    membership_history_complete: bool
    period_days: int

    def __post_init__(self) -> None:
        for field in (
            "total_messages",
            "active_users",
            "active_channels",
            "daily_active_users",
            "weekly_active_users",
            "monthly_active_users",
            "voice_users",
            "total_voice_minutes",
            "joins",
            "leaves",
            "joins_24h",
            "joins_7d",
            "joins_30d",
            "leaves_24h",
            "leaves_7d",
            "leaves_30d",
            "current_member_count",
            "moderation_events",
        ):
            _require_non_negative(getattr(self, field), field)
        if self.messages_per_active_user < 0:
            raise ValueError("messages_per_active_user must be non-negative.")
        if not 1 <= self.period_days <= 365:
            raise ValueError("period_days must be between 1 and 365.")


@dataclass(frozen=True, slots=True)
class ServerChannelStats:
    channel_id: str
    channel_name: str
    messages: int

    def __post_init__(self) -> None:
        if not self.channel_id.strip() or not self.channel_name.strip():
            raise ValueError("Channel identifier and name must not be blank.")
        _require_non_negative(self.messages, "messages")


@dataclass(frozen=True, slots=True)
class ServerHourlyStats:
    hour: int
    count: int

    def __post_init__(self) -> None:
        if isinstance(self.hour, bool) or not 0 <= self.hour <= 23:
            raise ValueError("hour must be between 0 and 23.")
        _require_non_negative(self.count, "count")


@dataclass(frozen=True, slots=True)
class ServerDailyStats:
    date: str
    count: int

    def __post_init__(self) -> None:
        if not self.date.strip():
            raise ValueError("date must not be blank.")
        _require_non_negative(self.count, "count")


@dataclass(frozen=True, slots=True)
class PlatformServerStats:
    platform: Platform
    summary: ServerStatsSummary
    channels: tuple[ServerChannelStats, ...]
    hourly: tuple[ServerHourlyStats, ...]
    daily: tuple[ServerDailyStats, ...]
