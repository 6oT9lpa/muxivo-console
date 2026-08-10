from uuid import uuid4

import pytest
from muxivo_console.application.get_platform_dashboard_summary import GetPlatformDashboardSummary
from muxivo_console.application.get_platform_health import PlatformHealthUnavailableError
from muxivo_console.application.list_control_modules import (
    AccessDeniedError,
    PlatformControlUnavailableError,
)
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.authorization import AuthorizationDecision
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection
from muxivo_console.domain.dashboard import PlatformDashboardSummary


class Authorizer:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed

    async def authorize(self, request) -> AuthorizationDecision:
        return AuthorizationDecision(allowed=self.allowed)


class ConnectionReader:
    def __init__(self, connection: PlatformConnection | None) -> None:
        self.connection = connection
        self.arguments = None

    async def find_for_organization(self, **kwargs) -> PlatformConnection | None:
        self.arguments = kwargs
        return self.connection


class DashboardReader:
    def __init__(self, summary: PlatformDashboardSummary) -> None:
        self.summary = summary
        self.arguments = None

    async def get_for_connection(self, **kwargs) -> PlatformDashboardSummary:
        self.arguments = kwargs
        return self.summary


def connection(status: ConnectionStatus = ConnectionStatus.ACTIVE) -> PlatformConnection:
    return PlatformConnection(
        id=uuid4(),
        organization_id=uuid4(),
        platform=Platform.DISCORD,
        external_resource_id="123456789",
        status=status,
    )


def summary(platform: Platform = Platform.DISCORD) -> PlatformDashboardSummary:
    return PlatformDashboardSummary(
        platform=platform,
        messages_today=120,
        ai_flagged_today=4,
        creator_sources=2,
        bot_latency_ms=45,
    )


@pytest.mark.asyncio
async def test_dashboard_summary_is_bound_to_owned_usable_connection() -> None:
    stored = connection()
    connections = ConnectionReader(stored)
    dashboard = DashboardReader(summary())
    use_case = GetPlatformDashboardSummary(Authorizer(), connections, dashboard)
    actor_id = uuid4()
    correlation_id = uuid4()

    result = await use_case.execute(
        actor_id=actor_id,
        organization_id=stored.organization_id,
        connection_id=stored.id,
        correlation_id=correlation_id,
    )

    assert result.messages_today == 120
    assert connections.arguments == {
        "organization_id": stored.organization_id,
        "connection_id": stored.id,
    }
    assert dashboard.arguments == {
        "organization_id": stored.organization_id,
        "actor_id": actor_id,
        "external_resource_id": "123456789",
        "correlation_id": correlation_id,
    }


@pytest.mark.asyncio
async def test_dashboard_summary_rejects_connection_that_is_not_usable() -> None:
    stored = connection(ConnectionStatus.PENDING)
    use_case = GetPlatformDashboardSummary(
        Authorizer(), ConnectionReader(stored), DashboardReader(summary())
    )

    with pytest.raises(PlatformHealthUnavailableError):
        await use_case.execute(
            actor_id=uuid4(),
            organization_id=stored.organization_id,
            connection_id=stored.id,
            correlation_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_dashboard_summary_rejects_cross_platform_adapter_response() -> None:
    stored = connection()
    use_case = GetPlatformDashboardSummary(
        Authorizer(), ConnectionReader(stored), DashboardReader(summary(Platform.TWITCH))
    )

    with pytest.raises(PlatformControlUnavailableError):
        await use_case.execute(
            actor_id=uuid4(),
            organization_id=stored.organization_id,
            connection_id=stored.id,
            correlation_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_dashboard_summary_requires_console_authorization_before_lookup() -> None:
    stored = connection()
    connections = ConnectionReader(stored)
    use_case = GetPlatformDashboardSummary(
        Authorizer(False), connections, DashboardReader(summary())
    )

    with pytest.raises(AccessDeniedError):
        await use_case.execute(
            actor_id=uuid4(),
            organization_id=stored.organization_id,
            connection_id=stored.id,
            correlation_id=uuid4(),
        )

    assert connections.arguments is None
