from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.ai_moderation import PlatformAiModerationSummary
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import create_app


class SessionResolver:
    def __init__(self, actor_id: UUID) -> None:
        self.actor_id = actor_id

    async def execute(self, _: str) -> BrowserSessionPrincipal:
        return BrowserSessionPrincipal(
            self.actor_id,
            uuid4(),
            SessionAssuranceLevel.RECENT_AUTHENTICATION,
            datetime(2026, 8, 19, 12, tzinfo=UTC),
        )


class PolicyUpdateUseCase:
    def __init__(self) -> None:
        self.arguments: dict[str, object] | None = None

    async def execute(self, **arguments: object) -> PlatformAiModerationSummary:
        self.arguments = arguments
        return PlatformAiModerationSummary(
            platform=Platform.DISCORD,
            enforcement_mode="SHADOW",
            test_mode=False,
            is_default_policy=False,
            covered_channel_count=2,
            log_channel_configured=True,
            label_count=1,
            blacklist_word_count=0,
            allowed_domain_count=0,
            automated_timeout_enabled=False,
            automated_kick_enabled=False,
            automated_ban_enabled=False,
        )


def test_updates_ai_moderation_policy_through_the_versioned_browser_contract() -> None:
    actor_id, organization_id, connection_id = uuid4(), uuid4(), uuid4()
    use_case = PolicyUpdateUseCase()
    client = TestClient(
        create_app(
            platform_ai_moderation_policy_update_use_case=use_case,
            session_resolver=SessionResolver(actor_id),
        )
    )
    client.cookies.set("__Host-muxivo_session", "opaque")
    client.cookies.set("__Host-muxivo_csrf", "csrf-token")

    response = client.put(
        f"/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/ai-moderation-policy",
        headers={"X-CSRF-Token": "csrf-token"},
        json={
            "labels": {
                "spam": {
                    "risk_threshold": 42.5,
                    "min_action": "LOG",
                    "max_action": "DELETE",
                }
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["enforcement_mode"] == "SHADOW"
    assert use_case.arguments is not None
    assert use_case.arguments["organization_id"] == organization_id
    assert use_case.arguments["connection_id"] == connection_id
    assert use_case.arguments["principal"].user_id == actor_id
    assert use_case.arguments["policy"].labels["spam"].risk_threshold == 42.5
    assert "external_resource_id" not in use_case.arguments
