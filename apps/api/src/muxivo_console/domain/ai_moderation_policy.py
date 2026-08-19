"""Portable AI moderation policy value objects owned by Console's domain."""

from dataclasses import dataclass, field
from enum import StrEnum

from muxivo_console.domain.activity import Platform


class AiModerationAction(StrEnum):
    IGNORE = "IGNORE"
    LOG = "LOG"
    REVIEW = "REVIEW"
    WARN = "WARN"
    DELETE = "DELETE"
    DELETE_WARN = "DELETE_WARN"
    TIMEOUT = "TIMEOUT"
    KICK = "KICK"
    BAN = "BAN"


class AiModerationEnforcementMode(StrEnum):
    SHADOW = "SHADOW"
    LIMITED = "LIMITED"
    ELEVATED = "ELEVATED"


_ACTION_RANK = {action: index for index, action in enumerate(AiModerationAction)}


@dataclass(frozen=True, slots=True)
class AiModerationLabelRule:
    risk_threshold: float
    min_action: AiModerationAction
    max_action: AiModerationAction

    def __post_init__(self) -> None:
        if not 0 <= self.risk_threshold <= 100:
            raise ValueError("AI moderation label risk threshold must be between 0 and 100.")
        if _ACTION_RANK[self.min_action] > _ACTION_RANK[self.max_action]:
            raise ValueError("AI moderation label minimum action cannot exceed maximum action.")


@dataclass(frozen=True, slots=True)
class PlatformAiModerationPolicy:
    """A complete policy, deliberately without platform HTTP or persistence concerns."""

    platform: Platform
    blacklist_words: tuple[str, ...] = ()
    allowed_domains: tuple[str, ...] = ()
    labels: dict[str, AiModerationLabelRule] = field(default_factory=dict)
    blacklist_action: AiModerationAction = AiModerationAction.DELETE_WARN
    unapproved_domain_action: AiModerationAction = AiModerationAction.REVIEW
    context_window_days: int = 30
    repeat_offender_threshold: int = 3
    repeat_offender_action: AiModerationAction = AiModerationAction.TIMEOUT
    escalation_enabled: bool = True
    escalation_score_threshold: float = 3.0
    escalation_half_life_days: float = 30.0
    excluded_user_ids: tuple[str, ...] = ()
    excluded_role_ids: tuple[str, ...] = ()
    excluded_channel_ids: tuple[str, ...] = ()
    exclude_bots: bool = True
    ocr_enabled: bool = False
    ocr_failure_mode: str = "SKIP"
    ocr_max_gif_frames: int = 6
    ocr_process_empty_result: bool = False
    test_mode: bool = False
    enforcement_mode: AiModerationEnforcementMode = AiModerationEnforcementMode.SHADOW
    limited_min_confidence: float = 0.95
    limited_hard_rule_labels: tuple[str, ...] = ("INVITE", "SCAM")
    beta_enforcement_acknowledged: bool = False
    allow_automated_timeout: bool = False
    allow_automated_kick: bool = False
    allow_automated_ban: bool = False

    def __post_init__(self) -> None:
        if self.platform is not Platform.DISCORD:
            raise ValueError("AI moderation policy is not supported by this platform.")
        if not 1 <= self.context_window_days <= 3650:
            raise ValueError("AI moderation context window must be between 1 and 3650 days.")
        if not 1 <= self.repeat_offender_threshold <= 1000:
            raise ValueError("AI moderation repeat-offender threshold must be between 1 and 1000.")
        if not 0.1 <= self.escalation_score_threshold <= 1000:
            raise ValueError("AI moderation escalation score threshold is invalid.")
        if not 1 <= self.escalation_half_life_days <= 3650:
            raise ValueError("AI moderation escalation half-life is invalid.")
        if not 0 <= self.limited_min_confidence <= 1:
            raise ValueError("AI moderation limited confidence must be between 0 and 1.")
        if self.ocr_failure_mode not in {"SKIP", "REVIEW"}:
            raise ValueError("AI moderation OCR failure mode is invalid.")
        if not 1 <= self.ocr_max_gif_frames <= 24:
            raise ValueError("AI moderation OCR GIF frame limit must be between 1 and 24.")
        if not self.limited_hard_rule_labels:
            raise ValueError("AI moderation limited hard-rule labels are required.")
        if (
            self.enforcement_mode is AiModerationEnforcementMode.ELEVATED
            and any(
                (
                    self.allow_automated_timeout,
                    self.allow_automated_kick,
                    self.allow_automated_ban,
                )
            )
            and not self.beta_enforcement_acknowledged
        ):
            raise ValueError("Elevated automated actions require acknowledgement.")


@dataclass(frozen=True, slots=True)
class PlatformAiModerationPolicyState:
    """The effective policy and whether it is inherited from the platform default."""

    policy: PlatformAiModerationPolicy
    is_default_policy: bool
