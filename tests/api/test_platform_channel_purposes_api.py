from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.channel_purposes import ChannelPurpose, PlatformChannelPurposes
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import create_app


class SessionResolver:
    def __init__(self, actor_id: UUID) -> None:
        self.actor_id = actor_id

    async def execute(self, raw_token: str) -> BrowserSessionPrincipal:
        return BrowserSessionPrincipal(self.actor_id, uuid4(), SessionAssuranceLevel.PASSWORD)


class ChannelPurposeUpdateUseCase:
    def __init__(self) -> None:
        self.arguments: dict[str, object] | None = None

    async def execute(self, **arguments: object) -> PlatformChannelPurposes:
        self.arguments = arguments
        return PlatformChannelPurposes(
            platform=Platform.DISCORD,
            assignments={ChannelPurpose.WELCOME: "10"},
        )


def test_updates_a_channel_purpose_through_the_versioned_browser_contract() -> None:
    actor_id, organization_id, connection_id = uuid4(), uuid4(), uuid4()
    use_case = ChannelPurposeUpdateUseCase()
    client = TestClient(
        create_app(
            platform_channel_purpose_update_use_case=use_case,
            session_resolver=SessionResolver(actor_id),
        )
    )
    client.cookies.set("__Host-muxivo_session", "opaque")
    client.cookies.set("__Host-muxivo_csrf", "csrf-token")

    response = client.put(
        f"/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/channel-purposes",
        headers={"X-CSRF-Token": "csrf-token"},
        json={"purpose": "welcome", "channel_id": "10"},
    )

    assert response.status_code == 200
    assert response.json()["items"] == [{"purpose": "welcome", "channel_id": "10"}]
    assert use_case.arguments is not None
    assert use_case.arguments["organization_id"] == organization_id
    assert use_case.arguments["connection_id"] == connection_id
    assert use_case.arguments["channel_id"] == "10"
    assert "external_resource_id" not in use_case.arguments


def test_rejects_a_non_discord_channel_identifier_before_invoking_the_use_case() -> None:
    use_case = ChannelPurposeUpdateUseCase()
    client = TestClient(
        create_app(
            platform_channel_purpose_update_use_case=use_case,
            session_resolver=SessionResolver(uuid4()),
        )
    )
    client.cookies.set("__Host-muxivo_session", "opaque")
    client.cookies.set("__Host-muxivo_csrf", "csrf-token")

    response = client.put(
        f"/api/v1/organizations/{uuid4()}/platform-connections/{uuid4()}/channel-purposes",
        headers={"X-CSRF-Token": "csrf-token"},
        json={"purpose": "welcome", "channel_id": "not-a-snowflake"},
    )

    assert response.status_code == 422
    assert use_case.arguments is None
