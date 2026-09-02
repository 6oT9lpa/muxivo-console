"""Manage the Console-owned lifecycle state of platform connections."""

import logging
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from muxivo_console.application.ports import (
    IdentifierGenerator,
    OrganizationAuthorizer,
    PlatformConnectionLifecycleWriter,
    PlatformConnectionReader,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.authorization import (
    AuthorizationAction,
    AuthorizationRequest,
    AuthorizationResource,
)
from muxivo_console.domain.connections import ConnectionStatus, PlatformConnection

logger = logging.getLogger(__name__)


class PlatformConnectionLifecycleRejectedError(PermissionError):
    """Safe failure for unauthorized, missing, or invalid lifecycle transitions."""


class PlatformConnectionLifecycleAction(StrEnum):
    REAUTHORIZE = "reauthorize"
    REVOKE = "revoke"
    DISCONNECT = "disconnect"

    @property
    def target_status(self) -> ConnectionStatus:
        if self is PlatformConnectionLifecycleAction.REAUTHORIZE:
            return ConnectionStatus.ACTIVE
        if self is PlatformConnectionLifecycleAction.REVOKE:
            return ConnectionStatus.REAUTH_REQUIRED
        return ConnectionStatus.DISCONNECTED

    @property
    def audit_action(self) -> str:
        return f"platform_connection.{self.value}"


@dataclass(frozen=True, slots=True)
class ManagePlatformConnectionLifecycleCommand:
    actor_id: UUID
    organization_id: UUID
    connection_id: UUID
    action: PlatformConnectionLifecycleAction
    correlation_id: UUID
    idempotency_key: str | None = None


@dataclass(slots=True)
class ManagePlatformConnectionLifecycle:
    authorizer: OrganizationAuthorizer
    connections: PlatformConnectionReader
    lifecycle: PlatformConnectionLifecycleWriter
    identifiers: IdentifierGenerator

    async def execute(
        self, command: ManagePlatformConnectionLifecycleCommand
    ) -> PlatformConnection:
        logger.info(
            "platform_connection.lifecycle.started",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(command.organization_id),
                "connection_id": str(command.connection_id),
                "action": command.action.value,
                "idempotency_key_present": command.idempotency_key is not None,
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
                "platform_connection.lifecycle.denied",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "connection_id": str(command.connection_id),
                    "action": command.action.value,
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise PlatformConnectionLifecycleRejectedError("Lifecycle action denied.")

        idempotency_key = _normalized_idempotency_key(command.idempotency_key)
        if idempotency_key is not None:
            idempotent_result = await self.lifecycle.find_idempotent_lifecycle_result(
                organization_id=command.organization_id,
                idempotency_key=idempotency_key,
            )
            if idempotent_result is not None:
                current = await self.connections.find_for_organization(
                    organization_id=command.organization_id,
                    connection_id=command.connection_id,
                )
                if (
                    current is None
                    or idempotent_result.connection_id != command.connection_id
                    or idempotent_result.action != command.action.value
                ):
                    logger.warning(
                        "platform_connection.lifecycle.idempotency_conflict",
                        extra={
                            "actor_id": str(command.actor_id),
                            "organization_id": str(command.organization_id),
                            "connection_id": str(command.connection_id),
                            "action": command.action.value,
                            "correlation_id": str(command.correlation_id),
                        },
                    )
                    raise PlatformConnectionLifecycleRejectedError(
                        "Lifecycle idempotency key conflicts with another request."
                    )
                logger.info(
                    "platform_connection.lifecycle.idempotency_replayed",
                    extra={
                        "actor_id": str(command.actor_id),
                        "organization_id": str(command.organization_id),
                        "connection_id": str(command.connection_id),
                        "action": command.action.value,
                        "result_status": idempotent_result.result_status.value,
                        "correlation_id": str(command.correlation_id),
                    },
                )
                return PlatformConnection(
                    id=current.id,
                    organization_id=current.organization_id,
                    platform=current.platform,
                    external_resource_id=current.external_resource_id,
                    status=idempotent_result.result_status,
                )

        current = await self.connections.find_for_organization(
            organization_id=command.organization_id,
            connection_id=command.connection_id,
        )
        if current is None:
            logger.warning(
                "platform_connection.lifecycle.not_found",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "connection_id": str(command.connection_id),
                    "action": command.action.value,
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise PlatformConnectionLifecycleRejectedError("Connection is unavailable.")

        target_status = command.action.target_status
        if current.status is target_status:
            logger.info(
                "platform_connection.lifecycle.noop",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "connection_id": str(command.connection_id),
                    "status": current.status.value,
                    "action": command.action.value,
                    "correlation_id": str(command.correlation_id),
                },
            )
            return current
        try:
            updated = current.transition_to(target_status)
        except ValueError as error:
            logger.warning(
                "platform_connection.lifecycle.invalid_transition",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "connection_id": str(command.connection_id),
                    "from_status": current.status.value,
                    "target_status": target_status.value,
                    "action": command.action.value,
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise PlatformConnectionLifecycleRejectedError(
                "Connection lifecycle transition is invalid."
            ) from error

        saved = await self.lifecycle.update_status(
            connection=updated,
            audit_event=AuditEvent(
                id=self.identifiers.new(),
                correlation_id=command.correlation_id,
                actor_id=command.actor_id,
                organization_id=command.organization_id,
                action=command.action.audit_action,
                resource_type="platform_connection",
                resource_id=str(command.connection_id),
                result="succeeded",
            ),
            idempotency_key=idempotency_key,
            idempotency_action=command.action.value if idempotency_key is not None else None,
        )
        if not saved:
            logger.warning(
                "platform_connection.lifecycle.conflict",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "connection_id": str(command.connection_id),
                    "action": command.action.value,
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise PlatformConnectionLifecycleRejectedError(
                "Connection lifecycle transition could not be saved."
            )
        logger.info(
            "platform_connection.lifecycle.completed",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(command.organization_id),
                "connection_id": str(command.connection_id),
                "status": updated.status.value,
                "action": command.action.value,
                "correlation_id": str(command.correlation_id),
            },
        )
        return updated


def _normalized_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > 128:
        raise PlatformConnectionLifecycleRejectedError("Idempotency key is too long.")
    return normalized
