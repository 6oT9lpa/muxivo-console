from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from muxivo_console.application.change_organization_member_role import (
    OrganizationMemberNotFoundError,
    OrganizationRoleChangeConflictError,
    OrganizationRoleChangeRejectedError,
)
from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.organizations import OrganizationMember, OrganizationRole
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    create_app,
)
from muxivo_console.presentation.organization_roles import create_organization_role_router


class SessionResolver:
    def __init__(self, actor_id: UUID) -> None:
        self.actor_id = actor_id

    async def execute(self, raw_token: str) -> BrowserSessionPrincipal:
        return BrowserSessionPrincipal(
            self.actor_id, uuid4(), SessionAssuranceLevel.PASSWORD
        )


class RoleChangeUseCase:
    def __init__(self, result: OrganizationMember | Exception) -> None:
        self.result = result
        self.command = None

    async def execute(self, command):
        self.command = command
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def mutation_headers(*, with_csrf: bool = True) -> dict[str, str]:
    cookie = f"{SESSION_COOKIE_NAME}=opaque-browser-session"
    headers = {"Cookie": cookie}
    if with_csrf:
        headers["Cookie"] = f"{cookie}; {CSRF_COOKIE_NAME}=csrf-token"
        headers[CSRF_HEADER_NAME] = "csrf-token"
    return headers


def client_for(use_case: RoleChangeUseCase, actor_id: UUID) -> TestClient:
    app = create_app(session_resolver=SessionResolver(actor_id))
    app.include_router(create_organization_role_router(use_case))
    return TestClient(app)


def test_updates_role_with_authenticated_actor_and_correlation_id() -> None:
    actor_id = uuid4()
    organization_id = uuid4()
    member = OrganizationMember(uuid4(), uuid4(), "Moderator", OrganizationRole.ANALYST)
    use_case = RoleChangeUseCase(member)

    response = client_for(use_case, actor_id).patch(
        f"/api/v1/organizations/{organization_id}/members/{member.membership_id}/role",
        json={"role": "analyst"},
        headers=mutation_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "membership_id": str(member.membership_id),
        "user_id": str(member.user_id),
        "display_name": "Moderator",
        "role": "analyst",
    }
    assert use_case.command.actor_id == actor_id
    assert use_case.command.organization_id == organization_id
    assert use_case.command.membership_id == member.membership_id
    assert use_case.command.role is OrganizationRole.ANALYST
    assert isinstance(use_case.command.correlation_id, UUID)


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (AccessDeniedError("denied"), 403, "Organization role change denied"),
        (
            OrganizationRoleChangeRejectedError("owner details"),
            403,
            "Organization role change denied",
        ),
        (OrganizationMemberNotFoundError("missing"), 404, "Organization member not found"),
        (
            OrganizationRoleChangeConflictError("stale"),
            409,
            "Organization membership changed; reload and retry",
        ),
    ],
)
def test_maps_role_change_errors_without_leaking_policy_details(
    error: Exception, status_code: int, detail: str
) -> None:
    use_case = RoleChangeUseCase(error)
    response = client_for(use_case, uuid4()).patch(
        f"/api/v1/organizations/{uuid4()}/members/{uuid4()}/role",
        json={"role": "viewer"},
        headers=mutation_headers(),
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


def test_role_change_is_csrf_protected() -> None:
    use_case = RoleChangeUseCase(
        OrganizationMember(uuid4(), uuid4(), "Viewer", OrganizationRole.VIEWER)
    )

    response = client_for(use_case, uuid4()).patch(
        f"/api/v1/organizations/{uuid4()}/members/{uuid4()}/role",
        json={"role": "viewer"},
        headers=mutation_headers(with_csrf=False),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF validation failed"}
    assert use_case.command is None


def test_role_change_requires_browser_session_after_csrf_validation() -> None:
    use_case = RoleChangeUseCase(
        OrganizationMember(uuid4(), uuid4(), "Viewer", OrganizationRole.VIEWER)
    )
    app = create_app()
    app.include_router(create_organization_role_router(use_case))

    response = TestClient(app).patch(
        f"/api/v1/organizations/{uuid4()}/members/{uuid4()}/role",
        json={"role": "viewer"},
        headers={
            "Cookie": f"{CSRF_COOKIE_NAME}=csrf-token",
            CSRF_HEADER_NAME: "csrf-token",
        },
    )

    assert response.status_code == 401
    assert use_case.command is None
