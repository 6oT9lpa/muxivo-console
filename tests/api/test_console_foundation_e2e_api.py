from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.create_browser_session import IssuedBrowserSession
from muxivo_console.application.list_organization_audit_events import AuditEventPage
from muxivo_console.application.list_platform_connections import PlatformConnectionPage
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.audit import AuditLogEntry
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection
from muxivo_console.domain.organizations import (
    Organization,
    OrganizationMembership,
    OrganizationMembershipProfile,
    OrganizationRole,
)
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import (
    CSRF_HEADER_NAME,
    BrowserSessionCookieSettings,
    create_app,
)


class FoundationSmokeState:
    def __init__(self) -> None:
        self.actor_id = uuid4()
        self.session_id = uuid4()
        self.raw_session_cookie = "foundation-smoke-session"
        self.csrf_token = "foundation-smoke-csrf"
        self.organization: Organization | None = None
        self.membership: OrganizationMembership | None = None
        self.connection: PlatformConnection | None = None
        self.audit_events: list[AuditLogEntry] = []

    def record_audit(
        self,
        *,
        action: str,
        organization_id: UUID,
        resource_type: str,
        resource_id: str | None,
    ) -> None:
        self.audit_events.append(
            AuditLogEntry(
                id=uuid4(),
                correlation_id=uuid4(),
                actor_id=self.actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                result="succeeded",
                created_at=datetime(2026, 8, 22, 12, len(self.audit_events), tzinfo=UTC),
            )
        )


class AuthenticationUseCase:
    def __init__(self, state: FoundationSmokeState) -> None:
        self.state = state

    async def execute(self, _) -> IssuedBrowserSession:
        return IssuedBrowserSession(
            id=self.state.session_id,
            raw_token=self.state.raw_session_cookie,
            raw_csrf_token=self.state.csrf_token,
            expires_at=datetime.now(UTC) + timedelta(days=14),
            assurance_level=SessionAssuranceLevel.PASSWORD,
        )


class SessionResolver:
    def __init__(self, state: FoundationSmokeState) -> None:
        self.state = state

    async def execute(self, raw_token: str) -> BrowserSessionPrincipal | None:
        if raw_token != self.state.raw_session_cookie:
            return None
        return BrowserSessionPrincipal(
            self.state.actor_id,
            self.state.session_id,
            SessionAssuranceLevel.PASSWORD,
        )


class OrganizationCreationUseCase:
    def __init__(self, state: FoundationSmokeState) -> None:
        self.state = state

    async def execute(self, command) -> Organization:
        organization = Organization(uuid4(), command.name, "creator-community")
        membership = OrganizationMembership(
            actor_id=self.state.actor_id,
            organization_id=organization.id,
            role=OrganizationRole.OWNER,
            id=uuid4(),
        )
        self.state.organization = organization
        self.state.membership = membership
        self.state.record_audit(
            action="organization.created",
            organization_id=organization.id,
            resource_type="organization",
            resource_id=str(organization.id),
        )
        return organization


class OrganizationListUseCase:
    def __init__(self, state: FoundationSmokeState) -> None:
        self.state = state

    async def execute(self, _) -> tuple[OrganizationMembershipProfile, ...]:
        if self.state.organization is None or self.state.membership is None:
            return ()
        return (
            OrganizationMembershipProfile(
                organization=self.state.organization,
                membership=self.state.membership,
            ),
        )


class PlatformConnectionRegistrationUseCase:
    def __init__(self, state: FoundationSmokeState) -> None:
        self.state = state

    async def execute(self, command) -> PlatformConnection:
        connection = PlatformConnection(
            id=uuid4(),
            organization_id=command.organization_id,
            platform=command.platform,
            external_resource_id=command.external_resource_id,
            status=ConnectionStatus.ACTIVE,
        )
        self.state.connection = connection
        self.state.record_audit(
            action="platform_connection.register",
            organization_id=command.organization_id,
            resource_type="platform_connection",
            resource_id=str(connection.id),
        )
        return connection


class PlatformConnectionListUseCase:
    def __init__(self, state: FoundationSmokeState) -> None:
        self.state = state

    async def execute(self, **_) -> PlatformConnectionPage:
        items = () if self.state.connection is None else (self.state.connection,)
        return PlatformConnectionPage(items=items, next_cursor=None)


class PlatformConnectionLifecycleUseCase:
    def __init__(self, state: FoundationSmokeState) -> None:
        self.state = state
        self.idempotency_key: str | None = None

    async def execute(self, command) -> PlatformConnection:
        if self.state.connection is None:
            raise AssertionError("Connection must exist before lifecycle action.")
        self.idempotency_key = command.idempotency_key
        updated = self.state.connection.transition_to(command.action.target_status)
        self.state.connection = updated
        self.state.record_audit(
            action=command.action.audit_action,
            organization_id=command.organization_id,
            resource_type="platform_connection",
            resource_id=str(command.connection_id),
        )
        return updated


class AuditEventsUseCase:
    def __init__(self, state: FoundationSmokeState) -> None:
        self.state = state

    async def execute(self, **_) -> AuditEventPage:
        return AuditEventPage(items=tuple(self.state.audit_events), next_cursor=None)


def test_sign_in_create_organization_connect_audit_and_revoke_foundation_flow() -> None:
    state = FoundationSmokeState()
    lifecycle = PlatformConnectionLifecycleUseCase(state)
    cookies = BrowserSessionCookieSettings.development()
    client = TestClient(
        create_app(
            authentication_use_case=AuthenticationUseCase(state),
            session_resolver=SessionResolver(state),
            organization_creation_use_case=OrganizationCreationUseCase(state),
            organization_list_use_case=OrganizationListUseCase(state),
            platform_connection_registration_use_case=PlatformConnectionRegistrationUseCase(state),
            platform_connections_use_case=PlatformConnectionListUseCase(state),
            platform_connection_lifecycle_use_case=lifecycle,
            audit_events_use_case=AuditEventsUseCase(state),
            browser_session_cookies=cookies,
        )
    )

    login = client.post(
        "/api/v1/auth/email-password/sessions",
        json={"email": "creator@example.com", "password": "a-long-enough-password"},
    )
    csrf_header = {CSRF_HEADER_NAME: state.csrf_token}

    assert login.status_code == 204
    assert client.cookies.get(cookies.session_name) == state.raw_session_cookie
    assert client.cookies.get(cookies.csrf_name) == state.csrf_token

    created_organization = client.post(
        "/api/v1/organizations",
        json={"name": "Creator community"},
        headers=csrf_header,
    )

    assert created_organization.status_code == 201
    organization_id = created_organization.json()["id"]

    organizations = client.get("/api/v1/organizations")

    assert organizations.status_code == 200
    assert organizations.json()["items"][0]["organization"]["id"] == organization_id
    assert organizations.json()["items"][0]["membership"]["role"] == "owner"

    registered_connection = client.post(
        f"/api/v1/organizations/{organization_id}/platform-connections",
        json={"platform": Platform.DISCORD.value, "external_resource_id": "123456789012345678"},
        headers=csrf_header,
    )

    assert registered_connection.status_code == 201
    connection_id = registered_connection.json()["id"]
    assert registered_connection.json()["status"] == "active"
    assert registered_connection.json()["granted_scopes"][0]["key"] == "discord.guild.read"
    assert registered_connection.json()["granted_scopes"][0]["status"] == "granted"
    assert "access_token" not in registered_connection.text
    assert "refresh_token" not in registered_connection.text

    listed_connections = client.get(f"/api/v1/organizations/{organization_id}/platform-connections")

    assert listed_connections.status_code == 200
    assert listed_connections.json()["items"][0]["id"] == connection_id
    assert listed_connections.json()["items"][0]["granted_scopes"][1]["status"] == "granted"

    audit_after_connect = client.get(f"/api/v1/organizations/{organization_id}/audit-events")

    assert audit_after_connect.status_code == 200
    assert [event["action"] for event in audit_after_connect.json()["items"]] == [
        "organization.created",
        "platform_connection.register",
    ]

    revoked_connection = client.post(
        f"/api/v1/organizations/{organization_id}/platform-connections/{connection_id}/revocations",
        headers={**csrf_header, "Idempotency-Key": "foundation-revoke-1"},
    )

    assert revoked_connection.status_code == 200
    assert revoked_connection.json()["status"] == "reauth_required"
    assert lifecycle.idempotency_key == "foundation-revoke-1"

    audit_after_revoke = client.get(f"/api/v1/organizations/{organization_id}/audit-events")

    assert audit_after_revoke.status_code == 200
    assert [event["action"] for event in audit_after_revoke.json()["items"]] == [
        "organization.created",
        "platform_connection.register",
        "platform_connection.revoke",
    ]
