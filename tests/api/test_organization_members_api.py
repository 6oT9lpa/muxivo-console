from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.list_organizations import OrganizationListRejectedError
from muxivo_console.application.manage_organization_members import (
    OrganizationMemberManagementRejectedError,
)
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.authorization import AuthorizationAction, AuthorizationResource
from muxivo_console.domain.organizations import (
    MembershipResourceScope,
    Organization,
    OrganizationMembership,
    OrganizationMembershipProfile,
    OrganizationRole,
)
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    create_app,
)


class SessionResolver:
    def __init__(self, principal: BrowserSessionPrincipal | None) -> None:
        self.principal = principal

    async def execute(self, raw_token: str) -> BrowserSessionPrincipal | None:
        return self.principal


class OrganizationListUseCase:
    def __init__(
        self, profiles: tuple[OrganizationMembershipProfile, ...], rejects: bool = False
    ) -> None:
        self.profiles = profiles
        self.rejects = rejects
        self.command = None

    async def execute(self, command):
        self.command = command
        if self.rejects:
            raise OrganizationListRejectedError("Access denied.")
        return self.profiles


class OrganizationMembersUseCase:
    def __init__(self, members: tuple[OrganizationMembership, ...], rejects: bool = False) -> None:
        self.members = members
        self.rejects = rejects
        self.command = None

    async def execute(self, command):
        self.command = command
        if self.rejects:
            raise OrganizationMemberManagementRejectedError("Access denied.")
        return self.members


class OrganizationMemberMutationUseCase:
    def __init__(
        self, membership: OrganizationMembership | None = None, rejects: bool = False
    ) -> None:
        self.membership = membership
        self.rejects = rejects
        self.command = None

    async def execute(self, command):
        self.command = command
        if self.rejects:
            raise OrganizationMemberManagementRejectedError("Access denied.")
        return self.membership


def principal(actor_id: UUID) -> BrowserSessionPrincipal:
    return BrowserSessionPrincipal(actor_id, uuid4(), SessionAssuranceLevel.PASSWORD)


def csrf_headers() -> dict[str, str]:
    return {
        "Cookie": f"{SESSION_COOKIE_NAME}=opaque-browser-session; {CSRF_COOKIE_NAME}=csrf-token",
        CSRF_HEADER_NAME: "csrf-token",
    }


def profile(actor_id: UUID, organization_id: UUID) -> OrganizationMembershipProfile:
    return OrganizationMembershipProfile(
        organization=Organization(organization_id, "Creator community", "creator-community"),
        membership=OrganizationMembership(
            id=uuid4(),
            actor_id=actor_id,
            organization_id=organization_id,
            role=OrganizationRole.OWNER,
        ),
    )


def member(user_id: UUID, organization_id: UUID) -> OrganizationMembership:
    return OrganizationMembership(
        id=uuid4(),
        actor_id=user_id,
        organization_id=organization_id,
        role=OrganizationRole.VIEWER,
        resource_scopes=frozenset(
            (
                MembershipResourceScope(
                    id=uuid4(),
                    resource=AuthorizationResource.CONTROL_MODULES,
                    action=AuthorizationAction.READ,
                ),
            )
        ),
    )


def test_lists_organizations_for_authenticated_actor() -> None:
    actor_id = uuid4()
    organization_id = uuid4()
    listing = OrganizationListUseCase((profile(actor_id, organization_id),))
    app = create_app(
        organization_list_use_case=listing,
        session_resolver=SessionResolver(principal(actor_id)),
    )
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-browser-session")

    response = client.get("/api/v1/organizations")

    assert response.status_code == 200
    assert response.json()["items"][0]["organization"] == {
        "id": str(organization_id),
        "name": "Creator community",
        "slug": "creator-community",
    }
    assert response.json()["items"][0]["membership"]["role"] == "owner"
    assert listing.command.actor_id == actor_id
    assert isinstance(listing.command.correlation_id, UUID)


def test_lists_organization_members() -> None:
    actor_id = uuid4()
    target_id = uuid4()
    organization_id = uuid4()
    members = OrganizationMembersUseCase((member(target_id, organization_id),))
    app = create_app(
        organization_members_use_case=members,
        session_resolver=SessionResolver(principal(actor_id)),
    )
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE_NAME, "opaque-browser-session")

    response = client.get(f"/api/v1/organizations/{organization_id}/members")

    assert response.status_code == 200
    assert response.json()["items"][0]["user_id"] == str(target_id)
    assert response.json()["items"][0]["resource_scopes"][0] == {
        "id": response.json()["items"][0]["resource_scopes"][0]["id"],
        "resource": "console.control_modules",
        "action": "read",
    }
    assert members.command.actor_id == actor_id
    assert members.command.organization_id == organization_id


def test_add_organization_member_builds_command_from_contract() -> None:
    actor_id = uuid4()
    target_id = uuid4()
    organization_id = uuid4()
    created = member(target_id, organization_id)
    add_member = OrganizationMemberMutationUseCase(created)
    app = create_app(
        organization_member_add_use_case=add_member,
        session_resolver=SessionResolver(principal(actor_id)),
    )
    client = TestClient(app)

    response = client.post(
        f"/api/v1/organizations/{organization_id}/members",
        json={
            "email": "creator@example.com",
            "role": "viewer",
            "resource_scopes": [{"resource": "console.control_modules", "action": "read"}],
        },
        headers=csrf_headers(),
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == str(target_id)
    assert add_member.command.actor_id == actor_id
    assert add_member.command.organization_id == organization_id
    assert add_member.command.email == "creator@example.com"
    assert add_member.command.role is OrganizationRole.VIEWER
    assert add_member.command.resource_scopes == (
        MembershipResourceScope(
            resource=AuthorizationResource.CONTROL_MODULES,
            action=AuthorizationAction.READ,
        ),
    )


def test_remove_organization_member_returns_no_content() -> None:
    actor_id = uuid4()
    target_id = uuid4()
    organization_id = uuid4()
    remove_member = OrganizationMemberMutationUseCase()
    app = create_app(
        organization_member_remove_use_case=remove_member,
        session_resolver=SessionResolver(principal(actor_id)),
    )
    client = TestClient(app)

    response = client.delete(
        f"/api/v1/organizations/{organization_id}/members/{target_id}",
        headers=csrf_headers(),
    )

    assert response.status_code == 204
    assert remove_member.command.actor_id == actor_id
    assert remove_member.command.organization_id == organization_id
    assert remove_member.command.user_id == target_id


def test_member_mutation_hides_rejection_reason() -> None:
    actor_id = uuid4()
    organization_id = uuid4()
    add_member = OrganizationMemberMutationUseCase(rejects=True)
    app = create_app(
        organization_member_add_use_case=add_member,
        session_resolver=SessionResolver(principal(actor_id)),
    )
    client = TestClient(app)

    response = client.post(
        f"/api/v1/organizations/{organization_id}/members",
        json={"email": "owner@example.com", "role": "owner", "resource_scopes": []},
        headers=csrf_headers(),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Organization member creation failed"}
