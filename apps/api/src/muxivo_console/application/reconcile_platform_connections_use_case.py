"""Run periodic reconciliation for Console-owned platform connection state."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.ports import (
    IdentifierGenerator,
    PlatformConnectionLifecycleWriter,
    PlatformConnectionReconciliationProbe,
    PlatformConnectionReconciliationReader,
)
from muxivo_console.application.reconcile_platform_connections_command import (
    ReconcilePlatformConnectionsCommand,
)
from muxivo_console.application.reconcile_platform_connections_result import (
    ReconcilePlatformConnectionsResult,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.connection_reconciliation import ConnectionReconciliationDecision
from muxivo_console.domain.connection_status_reason import ConnectionStatusReason
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection

logger = logging.getLogger("muxivo_console.application.reconcile_platform_connections")


@dataclass(slots=True)
class ReconcilePlatformConnections:
    """Apply safe, idempotent state transitions reported by platform probes."""

    connections: PlatformConnectionReconciliationReader
    probes: dict[str, PlatformConnectionReconciliationProbe]
    lifecycle: PlatformConnectionLifecycleWriter
    identifiers: IdentifierGenerator

    async def execute(
        self, command: ReconcilePlatformConnectionsCommand
    ) -> ReconcilePlatformConnectionsResult:
        logger.info(
            "platform_connection.reconciliation.started",
            extra={
                "system_actor_id": str(command.system_actor_id),
                "limit": command.limit,
                "correlation_id": str(command.correlation_id),
            },
        )
        inspected = changed = skipped = 0
        for connection in await self.connections.list_reconcilable(limit=command.limit):
            inspected += 1
            probe = self.probes.get(connection.platform.value)
            if probe is None:
                skipped += 1
                logger.warning(
                    "platform_connection.reconciliation.probe_missing",
                    extra={
                        "connection_id": str(connection.id),
                        "organization_id": str(connection.organization_id),
                        "platform": connection.platform.value,
                        "correlation_id": str(command.correlation_id),
                    },
                )
                continue
            decision = await probe.inspect_connection(
                connection=connection,
                correlation_id=command.correlation_id,
            )
            reconciled = await self._apply_decision(
                connection=connection,
                decision=decision,
                system_actor_id=command.system_actor_id,
                correlation_id=command.correlation_id,
            )
            if reconciled:
                changed += 1
            else:
                skipped += 1
        logger.info(
            "platform_connection.reconciliation.completed",
            extra={
                "system_actor_id": str(command.system_actor_id),
                "inspected": inspected,
                "changed": changed,
                "skipped": skipped,
                "correlation_id": str(command.correlation_id),
            },
        )
        return ReconcilePlatformConnectionsResult(
            inspected=inspected,
            changed=changed,
            skipped=skipped,
        )

    async def _apply_decision(
        self,
        *,
        connection: PlatformConnection,
        decision: ConnectionReconciliationDecision,
        system_actor_id: UUID,
        correlation_id: UUID,
    ) -> bool:
        if connection.status is ConnectionStatus.DISCONNECTED:
            return False
        if connection.status is decision.target_status:
            logger.info(
                "platform_connection.reconciliation.noop",
                extra={
                    "connection_id": str(connection.id),
                    "organization_id": str(connection.organization_id),
                    "status": connection.status.value,
                    "reason": decision.reason.value,
                    "correlation_id": str(correlation_id),
                },
            )
            return False
        try:
            updated = connection.transition_to(
                decision.target_status,
                reason=ConnectionStatusReason(decision.reason.value),
            )
        except ValueError:
            logger.warning(
                "platform_connection.reconciliation.invalid_transition",
                extra={
                    "connection_id": str(connection.id),
                    "organization_id": str(connection.organization_id),
                    "from_status": connection.status.value,
                    "target_status": decision.target_status.value,
                    "reason": decision.reason.value,
                    "correlation_id": str(correlation_id),
                },
            )
            return False
        saved = await self.lifecycle.update_status(
            connection=updated,
            audit_event=AuditEvent(
                id=self.identifiers.new(),
                correlation_id=correlation_id,
                actor_id=system_actor_id,
                organization_id=connection.organization_id,
                action="platform_connection.reconciled",
                resource_type="platform_connection",
                resource_id=str(connection.id),
                result="succeeded",
            ),
        )
        if not saved:
            logger.warning(
                "platform_connection.reconciliation.conflict",
                extra={
                    "connection_id": str(connection.id),
                    "organization_id": str(connection.organization_id),
                    "target_status": decision.target_status.value,
                    "reason": decision.reason.value,
                    "correlation_id": str(correlation_id),
                },
            )
            return False
        logger.info(
            "platform_connection.reconciliation.changed",
            extra={
                "connection_id": str(connection.id),
                "organization_id": str(connection.organization_id),
                "from_status": connection.status.value,
                "target_status": decision.target_status.value,
                "reason": decision.reason.value,
                "correlation_id": str(correlation_id),
            },
        )
        return True
