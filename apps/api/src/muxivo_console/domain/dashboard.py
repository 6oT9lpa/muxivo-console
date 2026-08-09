"""Small, platform-neutral dashboard summaries safe for browser display."""

from dataclasses import dataclass

from muxivo_console.domain.activity import Platform


@dataclass(frozen=True, slots=True)
class PlatformDashboardSummary:
    platform: Platform
    messages_today: int
    ai_flagged_today: int
    creator_sources: int
    bot_latency_ms: int | None

    def __post_init__(self) -> None:
        if any(
            value < 0
            for value in (
                self.messages_today,
                self.ai_flagged_today,
                self.creator_sources,
            )
        ):
            raise ValueError("Dashboard counters must not be negative.")
        if self.bot_latency_ms is not None and self.bot_latency_ms < 0:
            raise ValueError("Bot latency must not be negative.")
