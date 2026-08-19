"""Non-secret runtime settings that a platform may expose to Muxivo Console."""

from dataclasses import dataclass

from muxivo_console.domain.activity import Platform


@dataclass(frozen=True, slots=True)
class PlatformBotSettings:
    """A compact browser projection; platform directories have dedicated contracts."""

    platform: Platform
    subscription_tier: str
    activity_rotation_enabled: bool
    activity_rotation_interval_seconds: int
    retention_days: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        if not self.subscription_tier.strip():
            raise ValueError("Subscription tier must not be blank.")
        if self.activity_rotation_interval_seconds < 1:
            raise ValueError("Activity rotation interval must be positive.")
        if any(not key.strip() or value < 0 for key, value in self.retention_days):
            raise ValueError("Retention settings must have non-blank keys and non-negative days.")
