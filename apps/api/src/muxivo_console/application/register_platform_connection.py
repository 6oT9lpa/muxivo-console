"""Register a verified, non-secret platform connection for a Console organization."""

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
        decision = await self.authorizer.authorize(
            AuthorizationRequest(
                actor_id=command.actor_id,
                organization_id=command.organization_id,
                resource=AuthorizationResource.PLATFORM_CONNECTIONS,
                action=AuthorizationAction.MANAGE,
            )
        )
        if not decision.allowed:
            raise PlatformConnectionRegistrationRejectedError("Registration was denied.")

        external_resource_id = command.external_resource_id.strip()
        verified = await self.verifier.verify_registration(
            actor_id=command.actor_id,
            organization_id=command.organization_id,
            platform=command.platform,
            external_resource_id=external_resource_id,
            correlation_id=command.correlation_id,
        )
        if not verified:
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
            raise PlatformConnectionRegistrationRejectedError("Registration could not be created.")
        return connection
