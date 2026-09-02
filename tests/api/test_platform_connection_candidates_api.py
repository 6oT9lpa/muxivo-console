from uuid import uuid4

from fastapi.testclient import TestClient
from muxivo_console.application.list_control_modules import (
    AccessDeniedError,
    PlatformControlUnavailableError,
)
from muxivo_console.application.list_platform_connection_candidates import (
    ListPlatformConnectionCandidatesCommand,
)
from muxivo_console.application.resolve_browser_session import BrowserSessionPrincipal
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.platform_connection_candidate import PlatformConnectionCandidate
from muxivo_console.domain.platform_connection_candidate_catalog import (
    PlatformConnectionCandidateCatalog,
)
from muxivo_console.domain.sessions import SessionAssuranceLevel
from muxivo_console.presentation.api import SESSION_COOKIE_NAME, create_app


class SessionResolver:
    def __init__(self, principal: BrowserSessionPrincipal | None) -> None:
        self.principal = principal

    async def execute(self, raw_token: str) -> BrowserSessionPrincipal | None:
        return self.principal


class CandidateUseCase:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.command: ListPlatformConnectionCandidatesCommand | None = None

    async def execute(self, command: ListPlatformConnectionCandidatesCommand):
        self.command = command
        if self.error is not None:
            raise self.error
        return self.result


def candidate_catalog() -> PlatformConnectionCandidateCatalog:
    return PlatformConnectionCandidateCatalog(
        platform=Platform.DISCORD,
        identity_linked=True,
        items=(
            PlatformConnectionCandidate(
                platform=Platform.DISCORD,
                external_resource_id="123456789012345678",
                display_name="Muxivo Community",
            ),
        ),
    )


def test_candidate_route_requires_session() -> None:
    client = TestClient(create_app(platform_connection_candidates_use_case=CandidateUseCase()))

    response = client.get(
        f"/api/v1/organizations/{uuid4()}/platform-connection-candidates?platform=discord"
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Access denied"}


def test_candidate_route_returns_browser_safe_catalog_and_session_actor() -> None:
    actor_id, organization_id, correlation_id = uuid4(), uuid4(), uuid4()
    use_case = CandidateUseCase(candidate_catalog())
    client = TestClient(
        create_app(
            platform_connection_candidates_use_case=use_case,
            session_resolver=SessionResolver(
                BrowserSessionPrincipal(actor_id, uuid4(), SessionAssuranceLevel.PASSWORD)
            ),
        )
    )

    response = client.get(
        f"/api/v1/organizations/{organization_id}/platform-connection-candidates?platform=discord",
        cookies={SESSION_COOKIE_NAME: "opaque-session"},
        headers={"X-Correlation-ID": str(correlation_id)},
    )

    assert response.status_code == 200
    assert response.json() == {
        "platform": "discord",
        "identity_linked": True,
        "items": [
            {
                "platform": "discord",
                "external_resource_id": "123456789012345678",
                "display_name": "Muxivo Community",
            }
        ],
    }
    assert response.headers["cache-control"] == "no-store"
    assert use_case.command is not None
    assert use_case.command.actor_id == actor_id
    assert use_case.command.organization_id == organization_id
    assert use_case.command.platform is Platform.DISCORD
    assert "access_token" not in response.text
    assert "refresh_token" not in response.text


def test_candidate_route_hides_authorization_failure() -> None:
    client = TestClient(
        create_app(
            platform_connection_candidates_use_case=CandidateUseCase(
                error=AccessDeniedError("internal policy detail")
            ),
            session_resolver=SessionResolver(
                BrowserSessionPrincipal(uuid4(), uuid4(), SessionAssuranceLevel.PASSWORD)
            ),
        )
    )

    response = client.get(
        f"/api/v1/organizations/{uuid4()}/platform-connection-candidates?platform=twitch",
        cookies={SESSION_COOKIE_NAME: "opaque-session"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Access denied"}


def test_candidate_route_maps_control_api_failure_to_service_unavailable() -> None:
    client = TestClient(
        create_app(
            platform_connection_candidates_use_case=CandidateUseCase(
                error=PlatformControlUnavailableError("upstream token leaked")
            ),
            session_resolver=SessionResolver(
                BrowserSessionPrincipal(uuid4(), uuid4(), SessionAssuranceLevel.PASSWORD)
            ),
        )
    )

    response = client.get(
        f"/api/v1/organizations/{uuid4()}/platform-connection-candidates?platform=discord",
        cookies={SESSION_COOKIE_NAME: "opaque-session"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Platform control service is unavailable"}
    assert "upstream token leaked" not in response.text
