from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.accept_organization_invitation import (
    AcceptOrganizationInvitationCommand,
)
from muxivo_console.application.invite_organization_member import (
    InviteOrganizationMemberCommand,
    OrganizationInvitationCreationResult,
)
from muxivo_console.application.list_organization_invitations import (
    ListOrganizationInvitationsCommand,
)
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.application.revoke_organization_invitation import (
    RevokeOrganizationInvitationCommand,
)
from muxivo_console.domain.organization_invitations import (
    OrganizationInvitation,
    OrganizationInvitationDeliveryStatus,
)
from muxivo_console.domain.organizations import OrganizationMembership, OrganizationRole
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    create_app,
)

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


class SessionResolver:
    def __init__(self, principal: BrowserSessionPrincipal) -> None:
        self.principal = principal

    async def execute(self, raw_token: str) -> BrowserSessionPrincipal:
        return self.principal


class InvitationCreateUseCase:
    def __init__(self, result: OrganizationInvitationCreationResult) -> None:
        self.result = result
        self.command = None

    async def execute(self, command: InviteOrganizationMemberCommand):
        self.command = command
        return self.result


class InvitationListUseCase:
    def __init__(self, invitations: tuple[OrganizationInvitation, ...]) -> None:
        self.invitations = invitations
        self.command = None

    async def execute(self, command: ListOrganizationInvitationsCommand):
        self.command = command
        return self.invitations


class InvitationRevokeUseCase:
    def __init__(self) -> None:
        self.command = None

    async def execute(self, command: RevokeOrganizationInvitationCommand) -> None:
        self.command = command


class InvitationAcceptUseCase:
    def __init__(self, membership: OrganizationMembership) -> None:
        self.membership = membership
        self.command = None

    async def execute(self, command: AcceptOrganizationInvitationCommand):
        self.command = command
        return self.membership


def csrf_headers() -> dict[str, str]:
    return {
        "Cookie": f"{SESSION_COOKIE_NAME}=opaque-browser-session; {CSRF_COOKIE_NAME}=csrf-token",
        CSRF_HEADER_NAME: "csrf-token",
    }


def invitation(
    organization_id: UUID,
    *,
    delivery_status: OrganizationInvitationDeliveryStatus | None = None,
) -> OrganizationInvitation:
    return OrganizationInvitation(
        id=uuid4(),
        organization_id=organization_id,
        invited_by_user_id=uuid4(),
        email_lookup_hash="e" * 64,
        email_hint="i***@example.com",
        email_ciphertext=b"encrypted-email",
        token_hash="t" * 64,
        role=OrganizationRole.VIEWER,
        resource_scopes=frozenset(),
        expires_at=NOW + timedelta(days=7),
        created_at=NOW,
        delivery_status=delivery_status,
    )


def test_create_invitation_returns_secret_free_projection() -> None:
    actor_id, organization_id = uuid4(), uuid4()
    stored = invitation(organization_id)
    create = InvitationCreateUseCase(
        OrganizationInvitationCreationResult(invitation=stored, delivery_status="sent")
    )
    app = create_app(
        organization_invitation_create_use_case=create,
        session_resolver=SessionResolver(
            BrowserSessionPrincipal(actor_id, uuid4(), SessionAssuranceLevel.PASSWORD)
        ),
    )
    client = TestClient(app)

    response = client.post(
        f"/api/v1/organizations/{organization_id}/member-invitations",
        json={
            "email": "invitee@example.com",
            "role": "viewer",
            "resource_scopes": [],
        },
        headers=csrf_headers(),
    )

    assert response.status_code == 202
    assert response.json()["email_hint"] == "i***@example.com"
    assert response.json()["status"] == "pending"
    assert "token" not in response.json()
    assert create.command.actor_id == actor_id
    assert create.command.organization_id == organization_id


def test_list_invitations_returns_status_and_masked_email() -> None:
    actor_id, organization_id = uuid4(), uuid4()
    listing = InvitationListUseCase(
        (invitation(organization_id, delivery_status=OrganizationInvitationDeliveryStatus.SENT),)
    )
    app = create_app(
        organization_invitation_list_use_case=listing,
        session_resolver=SessionResolver(
            BrowserSessionPrincipal(actor_id, uuid4(), SessionAssuranceLevel.PASSWORD)
        ),
    )
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-browser-session")

    response = client.get(f"/api/v1/organizations/{organization_id}/member-invitations")

    assert response.status_code == 200
    assert response.json()["items"][0]["status"] == "pending"
    assert response.json()["items"][0]["email_hint"] == "i***@example.com"
    assert response.json()["items"][0]["delivery_status"] == "sent"
    assert listing.command.organization_id == organization_id


def test_revoke_invitation_returns_no_content() -> None:
    actor_id, organization_id = uuid4(), uuid4()
    invitation_id = uuid4()
    revoke = InvitationRevokeUseCase()
    app = create_app(
        organization_invitation_revoke_use_case=revoke,
        session_resolver=SessionResolver(
            BrowserSessionPrincipal(actor_id, uuid4(), SessionAssuranceLevel.PASSWORD)
        ),
    )
    client = TestClient(app)

    response = client.delete(
        f"/api/v1/organizations/{organization_id}/member-invitations/{invitation_id}",
        headers=csrf_headers(),
    )

    assert response.status_code == 204
    assert revoke.command.invitation_id == invitation_id


def test_accept_invitation_returns_created_membership_without_echoing_token() -> None:
    actor_id, organization_id = uuid4(), uuid4()
    accepted = OrganizationMembership(
        id=uuid4(), actor_id=actor_id, organization_id=organization_id, role=OrganizationRole.VIEWER
    )
    accept = InvitationAcceptUseCase(accepted)
    app = create_app(
        organization_invitation_accept_use_case=accept,
        session_resolver=SessionResolver(
            BrowserSessionPrincipal(actor_id, uuid4(), SessionAssuranceLevel.PASSWORD)
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/member-invitations/accept",
        json={"token": "opaque-invitation-token"},
        headers=csrf_headers(),
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == str(actor_id)
    assert accept.command.raw_token == "opaque-invitation-token"
