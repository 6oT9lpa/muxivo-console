from uuid import uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.application.list_organization_members import OrganizationMemberPage
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.organizations import OrganizationMember, OrganizationRole
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import create_app
from muxivo_console.presentation.organization_members import create_organization_member_router


class SessionResolver:
    async def execute(self, raw_token: str) -> BrowserSessionPrincipal:
        return BrowserSessionPrincipal(uuid4(), uuid4(), SessionAssuranceLevel.PASSWORD)


class MemberUseCase:
    def __init__(self, result: OrganizationMemberPage | Exception) -> None:
        self.result = result
        self.arguments = None

    async def execute(self, **arguments) -> OrganizationMemberPage:
        self.arguments = arguments
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def authenticated_client(use_case: MemberUseCase) -> TestClient:
    app = create_app(session_resolver=SessionResolver())
    app.include_router(create_organization_member_router(use_case))
    client = TestClient(app)
    client.cookies.set("__Host-muxivo_session", "opaque")
    return client


def test_returns_non_secret_tenant_member_projection() -> None:
    organization_id = uuid4()
    member = OrganizationMember(
        membership_id=uuid4(),
        user_id=uuid4(),
        display_name="Administrator",
        role=OrganizationRole.ADMIN,
    )
    use_case = MemberUseCase(OrganizationMemberPage((member,), None))

    response = authenticated_client(use_case).get(
        f"/api/v1/organizations/{organization_id}/members"
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "membership_id": str(member.membership_id),
                "user_id": str(member.user_id),
                "display_name": "Administrator",
                "role": "admin",
            }
        ],
        "next_cursor": None,
    }
    assert use_case.arguments["organization_id"] == organization_id


def test_maps_authorization_failure_to_forbidden() -> None:
    use_case = MemberUseCase(AccessDeniedError("denied"))

    response = authenticated_client(use_case).get(
        f"/api/v1/organizations/{uuid4()}/members"
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Organization member access denied"}


def test_requires_browser_session() -> None:
    app = create_app()
    app.include_router(
        create_organization_member_router(MemberUseCase(OrganizationMemberPage((), None)))
    )

    response = TestClient(app).get(f"/api/v1/organizations/{uuid4()}/members")

    assert response.status_code == 403
