from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.list_organization_audit_events import AuditEventPage
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.audit import AuditLogEntry
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import create_app


class SessionResolver:
    def __init__(self, actor_id: UUID) -> None:
        self.actor_id = actor_id

    async def execute(self, _: str) -> BrowserSessionPrincipal:
        return BrowserSessionPrincipal(self.actor_id, uuid4(), SessionAssuranceLevel.PASSWORD)


class AuditEventsUseCase:
    def __init__(self) -> None:
        self.arguments: dict[str, object] | None = None

    async def execute(self, **arguments: object) -> AuditEventPage:
        self.arguments = arguments
        event_id = uuid4()
        return AuditEventPage(
            items=(
                AuditLogEntry(
                    id=event_id,
                    correlation_id=uuid4(),
                    actor_id=uuid4(),
                    action="platform_ai_moderation_policy.updated",
                    resource_type="platform_connection",
                    resource_id="connection-id",
                    result="succeeded",
                    created_at=datetime(2026, 8, 19, 12, tzinfo=UTC),
                ),
            ),
            next_cursor=event_id,
        )


def test_lists_secret_free_audit_events_through_the_versioned_browser_contract() -> None:
    actor_id, organization_id = uuid4(), uuid4()
    use_case = AuditEventsUseCase()
    client = TestClient(
        create_app(audit_events_use_case=use_case, session_resolver=SessionResolver(actor_id))
    )
    client.cookies.set("__Host-muxivo_session", "opaque")

    response = client.get(f"/api/v1/organizations/{organization_id}/audit-events?limit=25")

    assert response.status_code == 200
    assert response.json()["items"][0]["action"] == "platform_ai_moderation_policy.updated"
    assert response.json()["next_cursor"] is not None
    assert use_case.arguments == {
        "actor_id": actor_id,
        "organization_id": organization_id,
        "after_id": None,
        "limit": 25,
    }
