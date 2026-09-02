"""Read aggregate platform health through a platform Control API."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.access_denied_error import AccessDeniedError
from muxivo_console.application.platform_health_unavailable_error import (
    PlatformHealthUnavailableError,
)
from muxivo_console.application.ports import (
    OrganizationAuthorizer,
    PlatformConnectionReader,
    PlatformHealthReader,
)
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)
from muxivo_console.domain.connections import ConnectionStatus
from muxivo_console.domain.health import PlatformHealth

logger = logging.getLogger("muxivo_console.application.get_platform_health")


@dataclass(slots=True)
class GetPlatformHealth:
    """Read health only from an authorized, non-disconnected platform connection."""

    authorizer: OrganizationAuthorizer
    connections: PlatformConnectionReader
    health_readers: Mapping[Platform, PlatformHealthReader]

    async def execute(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        platform: Platform,
        correlation_id: UUID,
    ) -> PlatformHealth:
        logger.info(
            "platform.health.get.started",
            extra={
                "actor_id": str(actor_id),
                "organization_id": str(organization_id),
                "platform": platform.value,
                "correlation_id": str(correlation_id),
            },
        )
        decision = await self.authorizer.authorize(
            AuthorizationRequest(
                actor_id=actor_id,
                organization_id=organization_id,
                resource=AuthorizationResource.CONTROL_MODULES,
                action=AuthorizationAction.READ,
            )
        )
        if not decision.allowed:
            logger.warning(
                "platform.health.get.denied_rbac",
                extra={
                    "actor_id": str(actor_id),
                    "organization_id": str(organization_id),
                    "platform": platform.value,
                    "correlation_id": str(correlation_id),
                },
            )
            raise AccessDeniedError("The actor is not allowed to view platform health.")
        connections = await self.connections.list_for_organization(
            organization_id=organization_id, after_id=None, limit=100
        )
        if not any(
            connection.platform is platform
            and connection.status in {ConnectionStatus.ACTIVE, ConnectionStatus.DEGRADED}
            for connection in connections
        ):
            logger.warning(
                "platform.health.get.no_usable_connection",
                extra={
                    "actor_id": str(actor_id),
                    "organization_id": str(organization_id),
                    "platform": platform.value,
                    "correlation_id": str(correlation_id),
                },
            )
            raise PlatformHealthUnavailableError("No usable platform connection exists.")
        health_reader = self.health_readers.get(platform)
        if health_reader is None:
            logger.error(
                "platform.health.get.adapter_missing",
                extra={
                    "organization_id": str(organization_id),
                    "platform": platform.value,
                    "correlation_id": str(correlation_id),
                },
            )
            raise PlatformHealthUnavailableError("No platform health adapter is available.")
        health = await health_reader.get_for_organization(
            organization_id=organization_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
        )
        logger.info(
            "platform.health.get.completed",
            extra={
                "actor_id": str(actor_id),
                "organization_id": str(organization_id),
                "platform": platform.value,
                "correlation_id": str(correlation_id),
            },
        )
        return health
