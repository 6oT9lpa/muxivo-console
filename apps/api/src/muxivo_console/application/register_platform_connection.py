"""Register a verified, non-secret platform connection for a Console organization."""

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.ports import (
    IdentifierGenerator,
    OrganizationAuthorizer,
    PlatformConnectionVerifier,
    PlatformConnectionWriter,
)
from muxivo_console.domain.activity import Platform
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection

logger = logging.getLogger(__name__)


class PlatformConnectionRegistrationRejectedError(PermissionError):
    """Safe failure for denied, unverified, or conflicting platform registrations."""


@dataclass(frozen=True, slots=True)
class RegisterPlatformConnectionCommand:
    actor_id: UUID
    organization_id: UUID
    platform: Platform
    external_resource_id: str
    correlation_id: UUID


@dataclass(slots=True)
class RegisterPlatformConnection:
    authorizer: OrganizationAuthorizer
    verifier: PlatformConnectionVerifier
    identifiers: IdentifierGenerator
    connections: PlatformConnectionWriter

    async def execute(self, command: RegisterPlatformConnectionCommand) -> PlatformConnection:
        external_resource_id = command.external_resource_id.strip()
        logger.info(
            "platform_connection.register.started",
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
                "platform_connection.register.denied_rbac",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "platform": command.platform.value,
                    "external_resource_id": external_resource_id,
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise PlatformConnectionRegistrationRejectedError("Registration was denied.")

        verified = await self.verifier.verify_registration(
            actor_id=command.actor_id,
            organization_id=command.organization_id,
            platform=command.platform,
            external_resource_id=external_resource_id,
            correlation_id=command.correlation_id,
        )
        if not verified:
            logger.warning(
                "platform_connection.register.denied_ownership",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "platform": command.platform.value,
                    "external_resource_id": external_resource_id,
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise PlatformConnectionRegistrationRejectedError("Registration was not verified.")

        connection = PlatformConnection(
            id=self.identifiers.new(),
            organization_id=command.organization_id,
            platform=command.platform,
            external_resource_id=external_resource_id,
            status=ConnectionStatus.PENDING,
        )
        created = await self.connections.create(
            connection=connection,
            audit_event=AuditEvent(
                id=self.identifiers.new(),
                correlation_id=command.correlation_id,
                actor_id=command.actor_id,
                organization_id=command.organization_id,
                action="platform_connection.register",
                resource_type="platform_connection",
                resource_id=str(connection.id),
                result="succeeded",
            ),
        )
        if not created:
            logger.warning(
                "platform_connection.register.conflict",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "platform": command.platform.value,
                    "external_resource_id": external_resource_id,
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise PlatformConnectionRegistrationRejectedError("Registration could not be created.")
        logger.info(
            "platform_connection.register.completed",
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


@dataclass(frozen=True, slots=True)
class PlatformConnectionVerifierRouter:
    """Dispatch ownership verification to the adapter for the requested platform."""

    verifiers: Mapping[Platform, PlatformConnectionVerifier]

    async def verify_registration(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        platform: Platform,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> bool:
        verifier = self.verifiers.get(platform)
        if verifier is None:
            logger.warning(
                "platform_connection.verify.unsupported_platform",
                extra={
                    "actor_id": str(actor_id),
                    "organization_id": str(organization_id),
                    "platform": platform.value,
                    "external_resource_id": external_resource_id,
                    "correlation_id": str(correlation_id),
                },
            )
            return False
        return await verifier.verify_registration(
            actor_id=actor_id,
            organization_id=organization_id,
            platform=platform,
            external_resource_id=external_resource_id,
            correlation_id=correlation_id,
        )
