from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.reconcile_platform_connections import (
    ReconcilePlatformConnections,
    ReconcilePlatformConnectionsCommand,
)
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.connection_reconciliation import (
    ConnectionReconciliationDecision,
    ConnectionReconciliationReason,
)
from muxivo_console.domain.connection_status_reason import ConnectionStatusReason
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection


@dataclass(slots=True)
class FakeConnectionReader:
    connections: tuple[PlatformConnection, ...]

    async def list_reconcilable(self, *, limit: int) -> tuple[PlatformConnection, ...]:
        return self.connections[:limit]


@dataclass(slots=True)
class FakeProbe:
    decisions: dict[UUID, ConnectionReconciliationDecision]

    async def inspect_connection(
        self, *, connection: PlatformConnection, correlation_id: UUID
    ) -> ConnectionReconciliationDecision:
        return self.decisions[connection.id]


@dataclass(slots=True)
class FakeLifecycleWriter:
    saved: list[tuple[PlatformConnection, AuditEvent]] = field(default_factory=list)
    should_save: bool = True

    async def update_status(
        self,
        *,
        connection: PlatformConnection,
        audit_event: AuditEvent,
        idempotency_key: str | None = None,
        idempotency_action: str | None = None,
    ) -> bool:
        self.saved.append((connection, audit_event))
        return self.should_save


@dataclass(slots=True)
class FakeIdentifiers:
    def new(self) -> UUID:
        return uuid4()


def connection(status: ConnectionStatus = ConnectionStatus.ACTIVE) -> PlatformConnection:
    return PlatformConnection(
        id=uuid4(),
        organization_id=uuid4(),
        platform=Platform.DISCORD,
        external_resource_id="123456789012345678",
        status=status,
    )


@pytest.mark.asyncio
async def test_reconciliation_updates_connection_statuses_and_records_audit() -> None:
    expired = connection(ConnectionStatus.ACTIVE)
    recovered = connection(ConnectionStatus.DEGRADED)
    lifecycle = FakeLifecycleWriter()
    worker = ReconcilePlatformConnections(
        connections=FakeConnectionReader((expired, recovered)),
        probes={
            Platform.DISCORD.value: FakeProbe(
                {
                    expired.id: ConnectionReconciliationDecision(
                        target_status=ConnectionStatus.REAUTH_REQUIRED,
                        reason=ConnectionReconciliationReason.TOKEN_EXPIRED,
                    ),
                    recovered.id: ConnectionReconciliationDecision(
                        target_status=ConnectionStatus.ACTIVE,
                        reason=ConnectionReconciliationReason.HEALTHY,
                    ),
                }
            )
        },
        lifecycle=lifecycle,
        identifiers=FakeIdentifiers(),
    )

    result = await worker.execute(
        ReconcilePlatformConnectionsCommand(
            system_actor_id=uuid4(),
            correlation_id=uuid4(),
        )
    )

    assert result.inspected == 2
    assert result.changed == 2
    assert result.skipped == 0
    assert [saved[0].status for saved in lifecycle.saved] == [
        ConnectionStatus.REAUTH_REQUIRED,
        ConnectionStatus.ACTIVE,
    ]
    assert [saved[0].status_reason for saved in lifecycle.saved] == [
        ConnectionStatusReason.TOKEN_EXPIRED,
        ConnectionStatusReason.HEALTHY,
    ]
    assert {saved[1].action for saved in lifecycle.saved} == {"platform_connection.reconciled"}


@pytest.mark.asyncio
async def test_reconciliation_skips_connections_without_platform_probe() -> None:
    stored = connection(ConnectionStatus.ACTIVE)
    lifecycle = FakeLifecycleWriter()
    worker = ReconcilePlatformConnections(
        connections=FakeConnectionReader((stored,)),
        probes={},
        lifecycle=lifecycle,
        identifiers=FakeIdentifiers(),
    )

    result = await worker.execute(
        ReconcilePlatformConnectionsCommand(system_actor_id=uuid4(), correlation_id=uuid4())
    )

    assert result.inspected == 1
    assert result.changed == 0
    assert result.skipped == 1
    assert lifecycle.saved == []


@pytest.mark.asyncio
async def test_reconciliation_moves_pending_connection_to_degraded_after_preflight_failure() -> (
    None
):
    pending = connection(ConnectionStatus.PENDING)
    lifecycle = FakeLifecycleWriter()
    worker = ReconcilePlatformConnections(
        connections=FakeConnectionReader((pending,)),
        probes={
            Platform.DISCORD.value: FakeProbe(
                {
                    pending.id: ConnectionReconciliationDecision(
                        target_status=ConnectionStatus.DEGRADED,
                        reason=ConnectionReconciliationReason.PREFLIGHT_FAILED,
                    )
                }
            )
        },
        lifecycle=lifecycle,
        identifiers=FakeIdentifiers(),
    )

    result = await worker.execute(
        ReconcilePlatformConnectionsCommand(system_actor_id=uuid4(), correlation_id=uuid4())
    )

    assert result.inspected == 1
    assert result.changed == 1
    assert result.skipped == 0
    assert lifecycle.saved[0][0].status is ConnectionStatus.DEGRADED
    assert lifecycle.saved[0][0].status_reason is ConnectionStatusReason.PREFLIGHT_FAILED
