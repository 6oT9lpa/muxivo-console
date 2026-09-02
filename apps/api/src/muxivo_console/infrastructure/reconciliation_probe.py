"""Platform reconciliation probes backed by existing Control API health readers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.list_control_modules import PlatformControlUnavailableError
from muxivo_console.application.ports import PlatformHealthReader
from muxivo_console.domain.connection_reconciliation import (
    ConnectionReconciliationDecision,
    ConnectionReconciliationReason,
)
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection
from muxivo_console.domain.health import HealthStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PlatformHealthReconciliationProbe:
    """Derive Console lifecycle status from non-secret platform health signals."""

    health_reader: PlatformHealthReader
    system_actor_id: UUID

    async def inspect_connection(
        self, *, connection: PlatformConnection, correlation_id: UUID
    ) -> ConnectionReconciliationDecision:
        logger.info(
            "platform_connection.reconciliation_probe.started",
            extra={
                "connection_id": str(connection.id),
                "organization_id": str(connection.organization_id),
                "platform": connection.platform.value,
                "correlation_id": str(correlation_id),
            },
        )
        try:
            health = await self.health_reader.get_for_organization(
                organization_id=connection.organization_id,
                actor_id=self.system_actor_id,
                correlation_id=correlation_id,
            )
        except PlatformControlUnavailableError:
            logger.warning(
                "platform_connection.reconciliation_probe.platform_unreachable",
                extra={
                    "connection_id": str(connection.id),
                    "organization_id": str(connection.organization_id),
                    "platform": connection.platform.value,
                    "correlation_id": str(correlation_id),
                },
            )
            return ConnectionReconciliationDecision(
                target_status=ConnectionStatus.DEGRADED,
                reason=ConnectionReconciliationReason.PLATFORM_UNREACHABLE,
            )
        if any(signal.status is HealthStatus.DEGRADED for signal in health.signals):
            return ConnectionReconciliationDecision(
                target_status=ConnectionStatus.DEGRADED,
                reason=ConnectionReconciliationReason.PREFLIGHT_FAILED,
            )
        return ConnectionReconciliationDecision(
            target_status=ConnectionStatus.ACTIVE,
            reason=ConnectionReconciliationReason.HEALTHY,
        )
