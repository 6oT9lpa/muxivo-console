"""Use case for connecting a verified, non-secret platform resource."""

import logging
from dataclasses import dataclass

from muxivo_console.application.connect_platform_connection_command import (
    ConnectPlatformConnectionCommand,
)
from muxivo_console.application.platform_connection_connect_error import (
    PlatformConnectionConnectRejectedError,
)
from muxivo_console.application.ports import (
    IdentifierGenerator,
    OrganizationAuthorizer,
    PlatformConnectionVerifier,
    PlatformConnectionWriter,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)
from muxivo_console.domain.connection_status_reason import ConnectionStatusReason
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection

logger = logging.getLogger("muxivo_console.application.connect_platform_connection")


@dataclass(slots=True)
class ConnectPlatformConnection:
    """Persist a pending connection only after RBAC and native ownership checks."""

    authorizer: OrganizationAuthorizer
    verifier: PlatformConnectionVerifier
    identifiers: IdentifierGenerator
    connections: PlatformConnectionWriter

    async def execute(self, command: ConnectPlatformConnectionCommand) -> PlatformConnection:
        external_resource_id = command.external_resource_id.strip()
        logger.info(
            "platform_connection.connect.started",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(command.organization_id),
                "platform": command.platform.value,
                "external_resource_id": external_resource_id,
                "correlation_id": str(command.correlation_id),
            },
        )
        decision = await self.authorizer.authorize(
            AuthorizationRequest(
                actor_id=command.actor_id,
                organization_id=command.organization_id,
                resource=AuthorizationResource.PLATFORM_CONNECTIONS,
                action=AuthorizationAction.MANAGE,
            )
        )
        if not decision.allowed:
            logger.warning(
                "platform_connection.connect.denied_rbac",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "platform": command.platform.value,
                    "external_resource_id": external_resource_id,
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise PlatformConnectionConnectRejectedError("Connection was denied.")

        verified = await self.verifier.verify_connection(
            actor_id=command.actor_id,
            organization_id=command.organization_id,
            platform=command.platform,
            external_resource_id=external_resource_id,
            correlation_id=command.correlation_id,
        )
        if not verified:
            logger.warning(
                "platform_connection.connect.denied_ownership",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "platform": command.platform.value,
                    "external_resource_id": external_resource_id,
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise PlatformConnectionConnectRejectedError("Connection was not verified.")

        connection = PlatformConnection(
            id=self.identifiers.new(),
            organization_id=command.organization_id,
            platform=command.platform,
            external_resource_id=external_resource_id,
            status=ConnectionStatus.PENDING,
            status_reason=ConnectionStatusReason.INITIAL_PENDING,
        )
        created = await self.connections.create(
            connection=connection,
            audit_event=AuditEvent(
                id=self.identifiers.new(),
                correlation_id=command.correlation_id,
                actor_id=command.actor_id,
                organization_id=command.organization_id,
                action="platform_connection.connect",
                resource_type="platform_connection",
                resource_id=str(connection.id),
                result="succeeded",
            ),
        )
        if not created:
            logger.warning(
                "platform_connection.connect.conflict",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "platform": command.platform.value,
                    "external_resource_id": external_resource_id,
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise PlatformConnectionConnectRejectedError("Connection could not be created.")
        logger.info(
            "platform_connection.connect.completed",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(command.organization_id),
                "connection_id": str(connection.id),
                "platform": command.platform.value,
                "external_resource_id": external_resource_id,
                "correlation_id": str(command.correlation_id),
            },
        )
        return connection
