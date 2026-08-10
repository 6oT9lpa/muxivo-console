from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.list_audit_events import AuditEntryPage
from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.audit import AuditEntry
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import create_app
from muxivo_console.presentation.audit_events import create_audit_event_router


class SessionResolver:
    def __init__(self, actor_id=None) -> None:
        self.actor_id = actor_id or uuid4()

    async def execute(self, raw_token: str) -> BrowserSessionPrincipal:
        return BrowserSessionPrincipal(
            self.actor_id, uuid4(), SessionAssuranceLevel.PASSWORD
        )


class AuditUseCase:
    def __init__(self, result: AuditEntryPage | Exception) -> None:
        self.result = result
        self.arguments = None

    async def execute(self, **arguments) -> AuditEntryPage:
        self.arguments = arguments
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def authenticated_client(use_case: AuditUseCase, actor_id=None) -> TestClient:
    app = create_app(session_resolver=SessionResolver(actor_id))
    app.include_router(create_audit_event_router(use_case))
    client = TestClient(app)
    client.cookies.set("__Host-muxivo_session", "opaque")
    return client


def test_returns_tenant_audit_projection_and_forwards_filters() -> None:
    organization_id = uuid4()
    actor_id = uuid4()
    filtered_actor_id = uuid4()
    entry = AuditEntry(
        id=uuid4(),
        correlation_id=uuid4(),
        actor_id=filtered_actor_id,
        organization_id=organization_id,
        action="organization.member.role_changed",
        resource_type="organization_membership",
        resource_id=str(uuid4()),
        result="succeeded",
        created_at=datetime(2026, 8, 10, 18, 0, tzinfo=UTC),
    )
    use_case = AuditUseCase(AuditEntryPage((entry,), entry.id))

    response = authenticated_client(use_case, actor_id).get(
        f"/api/v1/organizations/{organization_id}/audit-events",
        params={
            "actor_id": str(filtered_actor_id),
            "action": entry.action,
            "resource_type": entry.resource_type,
            "result": "succeeded",
            "limit": 25,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["id"] == str(entry.id)
    assert payload["items"][0]["organization_id"] == str(organization_id)
    assert payload["items"][0]["correlation_id"] == str(entry.correlation_id)
    assert payload["items"][0]["result"] == "succeeded"
    assert payload["next_cursor"] == str(entry.id)
    assert use_case.arguments == {
        "actor_id": actor_id,
        "organization_id": organization_id,
        "after_event_id": None,
        "filter_actor_id": filtered_actor_id,
        "action": entry.action,
        "resource_type": entry.resource_type,
        "result": "succeeded",
        "limit": 25,
    }


def test_maps_tenant_authorization_failure_to_forbidden() -> None:
    use_case = AuditUseCase(AccessDeniedError("denied"))

    response = authenticated_client(use_case).get(
        f"/api/v1/organizations/{uuid4()}/audit-events"
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Organization audit access denied"}


def test_requires_browser_session() -> None:
    app = create_app()
    app.include_router(create_audit_event_router(AuditUseCase(AuditEntryPage((), None))))

    response = TestClient(app).get(f"/api/v1/organizations/{uuid4()}/audit-events")

    assert response.status_code == 401
