from uuid import UUID, uuid4

import pytest
from muxivo_console.application.list_control_modules import PlatformControlUnavailableError
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.connection_reconciliation import ConnectionReconciliationReason
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection
from muxivo_console.domain.health import HealthSignal, HealthStatus, PlatformHealth
from muxivo_console.infrastructure.reconciliation_probe import PlatformHealthReconciliationProbe


class HealthReader:
    def __init__(self, health: PlatformHealth | None, *, unavailable: bool = False) -> None:
        self.health = health
        self.unavailable = unavailable
        self.actor_id: UUID | None = None

    async def get_for_organization(
        self, *, organization_id: UUID, actor_id: UUID, correlation_id: UUID
    ) -> PlatformHealth:
        self.actor_id = actor_id
        if self.unavailable:
            raise PlatformControlUnavailableError("unavailable")
        assert self.health is not None
        return self.health


def connection() -> PlatformConnection:
    return PlatformConnection(
        id=uuid4(),
        organization_id=uuid4(),
        platform=Platform.DISCORD,
        external_resource_id="123456789012345678",
        status=ConnectionStatus.ACTIVE,
    )


@pytest.mark.asyncio
async def test_health_reconciliation_probe_marks_healthy_connection_active() -> None:
    system_actor_id = uuid4()
    health_reader = HealthReader(
        PlatformHealth(
            platform=Platform.DISCORD,
            signals=(
                HealthSignal(
                    key="discord.bot",
                    display_name="Discord bot",
                    value="ok",
                    status=HealthStatus.OPERATIONAL,
                    latency_ms=10,
                ),
            ),
        )
    )
    probe = PlatformHealthReconciliationProbe(
        health_reader=health_reader,
        system_actor_id=system_actor_id,
    )

    decision = await probe.inspect_connection(connection=connection(), correlation_id=uuid4())

    assert decision.target_status is ConnectionStatus.ACTIVE
    assert decision.reason is ConnectionReconciliationReason.HEALTHY
    assert health_reader.actor_id == system_actor_id


@pytest.mark.asyncio
async def test_health_reconciliation_probe_marks_degraded_signal_degraded() -> None:
    probe = PlatformHealthReconciliationProbe(
        health_reader=HealthReader(
            PlatformHealth(
                platform=Platform.DISCORD,
                signals=(
                    HealthSignal(
                        key="discord.bot",
                        display_name="Discord bot",
                        value="slow",
                        status=HealthStatus.DEGRADED,
                        latency_ms=5000,
                    ),
                ),
            )
        ),
        system_actor_id=uuid4(),
    )

    decision = await probe.inspect_connection(connection=connection(), correlation_id=uuid4())

    assert decision.target_status is ConnectionStatus.DEGRADED
    assert decision.reason is ConnectionReconciliationReason.PREFLIGHT_FAILED


@pytest.mark.asyncio
async def test_health_reconciliation_probe_marks_unreachable_platform_degraded() -> None:
    probe = PlatformHealthReconciliationProbe(
        health_reader=HealthReader(None, unavailable=True),
        system_actor_id=uuid4(),
    )

    decision = await probe.inspect_connection(connection=connection(), correlation_id=uuid4())

    assert decision.target_status is ConnectionStatus.DEGRADED
    assert decision.reason is ConnectionReconciliationReason.PLATFORM_UNREACHABLE
