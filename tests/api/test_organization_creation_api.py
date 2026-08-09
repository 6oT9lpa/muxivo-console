from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.create_organization import OrganizationCreationRejectedError
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.organizations import Organization
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


class OrganizationCreationUseCase:
    def __init__(self, organization: Organization | None = None, rejects: bool = False) -> None:
        self.organization = organization
        self.rejects = rejects
        self.command = None

    async def execute(self, command):
        self.command = command
        if self.rejects:
            raise OrganizationCreationRejectedError("Creation rejected.")
        return self.organization


def csrf_headers() -> dict[str, str]:
    return {
        "Cookie": f"{SESSION_COOKIE_NAME}=opaque-browser-session; {CSRF_COOKIE_NAME}=csrf-token",
        CSRF_HEADER_NAME: "csrf-token",
    }


def test_create_organization_requires_authenticated_principal() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/organizations", json={"name": "Creator community"}, headers=csrf_headers()
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Access denied"}


def test_create_organization_uses_authenticated_actor_and_correlation_id() -> None:
    actor_id = uuid4()
    organization = Organization(uuid4(), "Creator community", "creator-community")
    creation = OrganizationCreationUseCase(organization)
    app = create_app(
        organization_creation_use_case=creation,
        session_resolver=SessionResolver(
            BrowserSessionPrincipal(actor_id, uuid4(), SessionAssuranceLevel.PASSWORD)
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/organizations",
        json={"name": " Creator community "},
        headers=csrf_headers(),
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": str(organization.id),
        "name": "Creator community",
        "slug": "creator-community",
    }
    assert creation.command.actor_id == actor_id
    assert creation.command.name == "Creator community"
    assert isinstance(creation.command.correlation_id, UUID)


def test_create_organization_fails_closed_when_runtime_wiring_is_missing() -> None:
    client = TestClient(
        create_app(
            session_resolver=SessionResolver(
                BrowserSessionPrincipal(uuid4(), uuid4(), SessionAssuranceLevel.PASSWORD)
            )
        )
    )

    response = client.post(
        "/api/v1/organizations", json={"name": "Creator community"}, headers=csrf_headers()
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Organization creation is unavailable"}


def test_create_organization_hides_domain_rejection_reason() -> None:
    client = TestClient(
        create_app(
            organization_creation_use_case=OrganizationCreationUseCase(rejects=True),
            session_resolver=SessionResolver(
                BrowserSessionPrincipal(uuid4(), uuid4(), SessionAssuranceLevel.PASSWORD)
            ),
        )
    )

    response = client.post(
        "/api/v1/organizations", json={"name": "Creator community"}, headers=csrf_headers()
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Organization creation failed"}
