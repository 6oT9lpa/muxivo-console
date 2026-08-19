"""Versioned browser contract for portable AI moderation policy configuration."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AiAction = Literal[
    "IGNORE", "LOG", "REVIEW", "WARN", "DELETE", "DELETE_WARN", "TIMEOUT", "KICK", "BAN"
]
EnforcementMode = Literal["SHADOW", "LIMITED", "ELEVATED"]


class AiModerationLabelRuleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_threshold: int = Field(ge=0, le=100)
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
