from uuid import uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.list_organizations import OrganizationAccessPage
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.organizations import (
    Organization,
    OrganizationAccess,
    OrganizationRole,
)
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import SESSION_COOKIE_NAME, create_app
from muxivo_console.presentation.organizations import create_organization_query_router


class SessionResolver:
    def __init__(self, principal: BrowserSessionPrincipal | None) -> None:
        self.principal = principal

    async def execute(self, raw_token: str) -> BrowserSessionPrincipal | None:
        return self.principal


class OrganizationQuery:
    def __init__(self, page: OrganizationAccessPage) -> None:
        self.page = page
        self.arguments = None

    async def execute(self, **kwargs) -> OrganizationAccessPage:
        self.arguments = kwargs
        return self.page


def test_organization_discovery_returns_only_use_case_membership_projection() -> None:
    actor_id = uuid4()
    principal = BrowserSessionPrincipal(
        user_id=actor_id,
        session_id=uuid4(),
        assurance_level=SessionAssuranceLevel.PASSWORD,
    )
    organization = Organization(id=uuid4(), name="Creator team", slug="creator-team")
    query = OrganizationQuery(
        OrganizationAccessPage(
            items=(OrganizationAccess(organization, OrganizationRole.ADMIN),),
            next_cursor=None,
        )
    )
    app = create_app(session_resolver=SessionResolver(principal))
    app.include_router(create_organization_query_router(query))
    client = TestClient(app, base_url="https://testserver")

    response = client.get(
        "/api/v1/organizations?limit=25",
        headers={"Cookie": f"{SESSION_COOKIE_NAME}=opaque-session"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": str(organization.id),
                "name": "Creator team",
                "slug": "creator-team",
                "role": "admin",
            }
        ],
        "next_cursor": None,
    }
    assert query.arguments == {
        "actor_id": actor_id,
        "after_organization_id": None,
        "limit": 25,
    }


def test_organization_discovery_rejects_anonymous_browser() -> None:
    query = OrganizationQuery(OrganizationAccessPage(items=(), next_cursor=None))
    app = create_app(session_resolver=SessionResolver(None))
    app.include_router(create_organization_query_router(query))
    client = TestClient(app, base_url="https://testserver")

    response = client.get("/api/v1/organizations")

    assert response.status_code == 401
    assert query.arguments is None
