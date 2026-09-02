from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.get_platform_health import PlatformHealthUnavailableError
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.audit_timeline import PlatformAuditTimeline, PlatformAuditTimelineEvent
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import create_app


class SessionResolver:
    def __init__(self, actor_id: UUID) -> None:
        self.actor_id = actor_id

    async def execute(self, _: str) -> BrowserSessionPrincipal:
        return BrowserSessionPrincipal(self.actor_id, uuid4(), SessionAssuranceLevel.PASSWORD)


class AuditTimelineUseCase:
    def __init__(self, result: PlatformAuditTimeline | Exception) -> None:
        self.result = result

    async def execute(self, **_: object) -> PlatformAuditTimeline:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def client_for(actor_id: UUID, result: PlatformAuditTimeline | Exception) -> TestClient:
    client = TestClient(
        create_app(
            platform_audit_timeline_use_case=AuditTimelineUseCase(result),
            session_resolver=SessionResolver(actor_id),
        )
    )
    client.cookies.set("__Host-muxivo_session", "opaque")
    return client


def test_returns_sanitized_platform_audit_timeline() -> None:
    organization_id, connection_id = uuid4(), uuid4()
    response = client_for(
        uuid4(),
        PlatformAuditTimeline(
            Platform.DISCORD,
            (PlatformAuditTimelineEvent("channel_purpose_updated", "2026-08-19T12:00:00+00:00"),),
            20,
        ),
    ).get(
        f"/api/v1/organizations/{organization_id}/platform-connections/"
        f"{connection_id}/audit-timeline"
    )

    assert response.status_code == 200
    assert response.json() == {
        "organization_id": str(organization_id),
        "connection_id": str(connection_id),
        "platform": "discord",
        "items": [
            {
                "event_type": "channel_purpose_updated",
                "occurred_at": "2026-08-19T12:00:00+00:00",
            }
        ],
        "limit": 20,
    }
    assert "actor_id" not in response.text
    assert "details" not in response.text


def test_hides_unavailable_audit_timeline_connection_details() -> None:
    response = client_for(
        uuid4(),
        PlatformHealthUnavailableError("not available"),
    ).get(f"/api/v1/organizations/{uuid4()}/platform-connections/{uuid4()}/audit-timeline")

    assert response.status_code == 404
    assert response.json() == {"detail": "Platform audit timeline is unavailable"}
