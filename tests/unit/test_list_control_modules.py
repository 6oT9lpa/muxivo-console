from uuid import UUID, uuid4

import pytest
from muxivo_console.application.list_control_modules import AccessDeniedError, ListControlModules
from muxivo_console.domain.activity import (
    ControlModule,
    ModuleCapability,
    ModuleStatus,
    Platform,
)
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationDecision,
    AuthorizationRequest,
    AuthorizationResource,
)


class AllowAuthorizer:
    async def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        return AuthorizationDecision.allow()


class DenyAuthorizer:
    async def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
        return AuthorizationDecision.deny()


class RecordingCatalog:
    def __init__(self) -> None:
        self.called = False

    async def list_for_organization(
        self, *, organization_id: UUID, actor_id: UUID, correlation_id: UUID
    ):
        self.called = True
        return [
            ControlModule(
                key="discord.logs",
                display_name="Audit log",
                platform=Platform.DISCORD,
                capability=ModuleCapability.VIEW,
                status=ModuleStatus.AVAILABLE,
            )
        ]


@pytest.mark.asyncio
async def test_lists_modules_only_after_organization_authorization() -> None:
    catalog = RecordingCatalog()
    result = await ListControlModules(AllowAuthorizer(), catalog).execute(
        actor_id=uuid4(), organization_id=uuid4(), correlation_id=uuid4()
    )
    assert catalog.called is True
    assert result[0].key == "discord.logs"


@pytest.mark.asyncio
async def test_authorizes_the_exact_actor_organization_resource_and_action() -> None:
    class RecordingAuthorizer:
        request: AuthorizationRequest | None = None

        async def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision:
            self.request = request
            return AuthorizationDecision.allow()

    authorizer = RecordingAuthorizer()
    actor_id = uuid4()
    organization_id = uuid4()

    await ListControlModules(authorizer, RecordingCatalog()).execute(
        actor_id=actor_id, organization_id=organization_id, correlation_id=uuid4()
    )

    assert authorizer.request == AuthorizationRequest(
        actor_id=actor_id,
        organization_id=organization_id,
        resource=AuthorizationResource.CONTROL_MODULES,
        action=AuthorizationAction.READ,
    )


@pytest.mark.asyncio
async def test_does_not_call_platform_adapter_when_access_is_denied() -> None:
    catalog = RecordingCatalog()
    with pytest.raises(AccessDeniedError):
        await ListControlModules(DenyAuthorizer(), catalog).execute(
            actor_id=uuid4(), organization_id=uuid4(), correlation_id=uuid4()
        )
    assert catalog.called is False
