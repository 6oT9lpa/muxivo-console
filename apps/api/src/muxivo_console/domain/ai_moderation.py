"""Browser-safe AI moderation policy state shared across platform adapters."""

from dataclasses import dataclass

from muxivo_console.domain.activity import Platform


@dataclass(frozen=True, slots=True)
class PlatformAiModerationSummary:
    platform: Platform
    enforcement_mode: str
    test_mode: bool
    is_default_policy: bool
    covered_channel_count: int
    log_channel_configured: bool
    label_count: int
    blacklist_word_count: int
    allowed_domain_count: int
    automated_timeout_enabled: bool
    automated_kick_enabled: bool
    automated_ban_enabled: bool

    def __post_init__(self) -> None:
        if not self.enforcement_mode.strip():
            raise ValueError("AI moderation enforcement mode must be non-empty.")
        if any(
            value < 0
            for value in (
                self.covered_channel_count,
                self.label_count,
                self.blacklist_word_count,
                self.allowed_domain_count,
            )
        ):
            raise ValueError("AI moderation counts must not be negative.")
