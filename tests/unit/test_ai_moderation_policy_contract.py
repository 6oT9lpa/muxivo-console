import pytest
from muxivo_console.contracts.v1.ai_moderation_policy import (
    AiModerationPolicyUpdateRequest,
)
from pydantic import ValidationError


def test_policy_contract_accepts_safe_shadow_defaults() -> None:
    policy = AiModerationPolicyUpdateRequest()

    assert policy.enforcement_mode == "SHADOW"
    assert policy.allow_automated_ban is False


def test_policy_contract_rejects_elevated_automated_action_without_acknowledgement() -> None:
    with pytest.raises(ValidationError, match="require acknowledgement"):
        AiModerationPolicyUpdateRequest(enforcement_mode="ELEVATED", allow_automated_ban=True)
