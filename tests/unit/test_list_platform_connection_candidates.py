from uuid import uuid4

import pytest
from muxivo_console.application.list_control_modules import AccessDeniedError
from muxivo_console.application.list_platform_connection_candidates import (
    ListPlatformConnectionCandidates,
    ListPlatformConnectionCandidatesCommand,
)
from muxivo_console.application.platform_connection_candidate_catalog_router import (
    PlatformConnectionCandidateCatalogRouter,
)
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.authorization import AuthorizationAction, AuthorizationDecision
from muxivo_console.domain.platform_connection_candidate import PlatformConnectionCandidate
from muxivo_console.domain.platform_connection_candidate_catalog import (
    PlatformConnectionCandidateCatalog,
)


class Authorizer:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.request = None

    async def authorize(self, request):
        self.request = request
        return AuthorizationDecision(self.allowed)


class CandidateReader:
    def __init__(self, catalog: PlatformConnectionCandidateCatalog) -> None:
        self.catalog = catalog
        self.arguments = None

    async def list_for_platform(self, **arguments):
        self.arguments = arguments
        return self.catalog


def catalog() -> PlatformConnectionCandidateCatalog:
    return PlatformConnectionCandidateCatalog(
        platform=Platform.DISCORD,
        items=(
            PlatformConnectionCandidate(
                platform=Platform.DISCORD,
                external_resource_id="123456789012345678",
                display_name="Muxivo Community",
            ),
        ),
        identity_linked=True,
    )


@pytest.mark.asyncio
async def test_authorized_candidate_reader_uses_platform_and_returns_safe_catalog() -> None:
    actor_id, organization_id, correlation_id = uuid4(), uuid4(), uuid4()
    authorizer = Authorizer(True)
    reader = CandidateReader(catalog())
    command = ListPlatformConnectionCandidatesCommand(
        actor_id=actor_id,
        organization_id=organization_id,
        platform=Platform.DISCORD,
        correlation_id=correlation_id,
    )

    result = await ListPlatformConnectionCandidates(authorizer, reader).execute(command)

    assert result == catalog()
    assert reader.arguments == {
        "organization_id": organization_id,
        "actor_id": actor_id,
        "platform": Platform.DISCORD,
        "correlation_id": correlation_id,
    }
    assert authorizer.request.resource.value == "console.platform_connections"
    assert authorizer.request.action is AuthorizationAction.MANAGE


@pytest.mark.asyncio
async def test_denied_candidate_reader_never_calls_platform_adapter() -> None:
    reader = CandidateReader(catalog())
    command = ListPlatformConnectionCandidatesCommand(
        actor_id=uuid4(),
        organization_id=uuid4(),
        platform=Platform.DISCORD,
        correlation_id=uuid4(),
    )

    with pytest.raises(AccessDeniedError):
        await ListPlatformConnectionCandidates(Authorizer(False), reader).execute(command)

    assert reader.arguments is None


@pytest.mark.asyncio
async def test_router_fails_closed_for_platform_without_candidate_adapter() -> None:
    router = PlatformConnectionCandidateCatalogRouter({})

    with pytest.raises(RuntimeError, match="candidate catalog"):
        await router.list_for_platform(
            organization_id=uuid4(),
            actor_id=uuid4(),
            platform=Platform.TELEGRAM,
            correlation_id=uuid4(),
        )
