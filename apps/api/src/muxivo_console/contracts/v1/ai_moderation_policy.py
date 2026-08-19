"""Versioned browser contract for portable AI moderation policy configuration."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from muxivo_console.domain.activity import Platform
from muxivo_console.domain.ai_moderation_policy import (
    AiModerationAction as DomainAiModerationAction,
)
from muxivo_console.domain.ai_moderation_policy import (
    AiModerationEnforcementMode,
    AiModerationLabelRule,
    PlatformAiModerationPolicy,
)

AiAction = Literal[
    "IGNORE", "LOG", "REVIEW", "WARN", "DELETE", "DELETE_WARN", "TIMEOUT", "KICK", "BAN"
]
EnforcementMode = Literal["SHADOW", "LIMITED", "ELEVATED"]


class AiModerationLabelRuleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_threshold: float = Field(ge=0, le=100)
    min_action: AiAction
    max_action: AiAction


class AiModerationPolicyUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blacklist_words: list[str] = Field(default_factory=list, max_length=200)
    allowed_domains: list[str] = Field(default_factory=list, max_length=200)
    labels: dict[str, AiModerationLabelRuleRequest] = Field(default_factory=dict, max_length=32)
    blacklist_action: AiAction = "DELETE_WARN"
    unapproved_domain_action: AiAction = "REVIEW"
    context_window_days: int = Field(default=30, ge=1, le=3650)
    repeat_offender_threshold: int = Field(default=3, ge=1, le=1000)
    repeat_offender_action: AiAction = "TIMEOUT"
    escalation_enabled: bool = True
    escalation_score_threshold: float = Field(default=3, ge=0.1, le=1000)
    escalation_half_life_days: float = Field(default=30, ge=1, le=3650)
    excluded_user_ids: list[str] = Field(default_factory=list, max_length=500)
    excluded_role_ids: list[str] = Field(default_factory=list, max_length=500)
    excluded_channel_ids: list[str] = Field(default_factory=list, max_length=500)
    exclude_bots: bool = True
    ocr_enabled: bool = False
    ocr_failure_mode: Literal["SKIP", "REVIEW"] = "SKIP"
    ocr_max_gif_frames: int = Field(default=6, ge=1, le=24)
    ocr_process_empty_result: bool = False
    test_mode: bool = False
    enforcement_mode: EnforcementMode = "SHADOW"
    limited_min_confidence: float = Field(default=0.95, ge=0, le=1)
    limited_hard_rule_labels: list[str] = Field(default_factory=lambda: ["INVITE", "SCAM"])
    beta_enforcement_acknowledged: bool = False
    allow_automated_timeout: bool = False
    allow_automated_kick: bool = False
    allow_automated_ban: bool = False

    @model_validator(mode="after")
    def require_explicit_elevated_acknowledgement(self) -> "AiModerationPolicyUpdateRequest":
        if (
            self.enforcement_mode == "ELEVATED"
            and (
                self.allow_automated_timeout
                or self.allow_automated_kick
                or self.allow_automated_ban
            )
            and not self.beta_enforcement_acknowledged
        ):
            raise ValueError("Elevated automated actions require acknowledgement.")
        return self

    def to_domain_policy(self) -> PlatformAiModerationPolicy:
        return PlatformAiModerationPolicy(
            platform=Platform.DISCORD,
            blacklist_words=tuple(self.blacklist_words),
            allowed_domains=tuple(self.allowed_domains),
            labels={
                label: AiModerationLabelRule(
                    risk_threshold=rule.risk_threshold,
                    min_action=DomainAiModerationAction(rule.min_action),
                    max_action=DomainAiModerationAction(rule.max_action),
                )
                for label, rule in self.labels.items()
            },
            blacklist_action=DomainAiModerationAction(self.blacklist_action),
            unapproved_domain_action=DomainAiModerationAction(self.unapproved_domain_action),
            context_window_days=self.context_window_days,
            repeat_offender_threshold=self.repeat_offender_threshold,
            repeat_offender_action=DomainAiModerationAction(self.repeat_offender_action),
            escalation_enabled=self.escalation_enabled,
            escalation_score_threshold=self.escalation_score_threshold,
            escalation_half_life_days=self.escalation_half_life_days,
            excluded_user_ids=tuple(self.excluded_user_ids),
            excluded_role_ids=tuple(self.excluded_role_ids),
            excluded_channel_ids=tuple(self.excluded_channel_ids),
            exclude_bots=self.exclude_bots,
            ocr_enabled=self.ocr_enabled,
            ocr_failure_mode=self.ocr_failure_mode,
            ocr_max_gif_frames=self.ocr_max_gif_frames,
            ocr_process_empty_result=self.ocr_process_empty_result,
            test_mode=self.test_mode,
            enforcement_mode=AiModerationEnforcementMode(self.enforcement_mode),
            limited_min_confidence=self.limited_min_confidence,
            limited_hard_rule_labels=tuple(self.limited_hard_rule_labels),
            beta_enforcement_acknowledged=self.beta_enforcement_acknowledged,
            allow_automated_timeout=self.allow_automated_timeout,
            allow_automated_kick=self.allow_automated_kick,
            allow_automated_ban=self.allow_automated_ban,
        )
