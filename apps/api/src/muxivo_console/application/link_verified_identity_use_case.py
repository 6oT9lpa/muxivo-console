"""Use case for linking a trusted provider subject to an active Console user."""

import logging
from dataclasses import dataclass

from muxivo_console.application.identity_link_error import IdentityLinkRejectedError
from muxivo_console.application.link_verified_identity_command import LinkVerifiedIdentityCommand
from muxivo_console.application.ports import (
    IdentifierGenerator,
    LoginIdentityLinkWriter,
    UserStatusReader,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import LoginIdentity, LoginIdentityProvider, UserStatus

logger = logging.getLogger("muxivo_console.application.link_verified_identity")


@dataclass(slots=True)
class LinkVerifiedIdentity:
    """Persist a provider identity only after adapter verification and status checks."""

    identifiers: IdentifierGenerator
    user_statuses: UserStatusReader
    identities: LoginIdentityLinkWriter

    async def execute(self, command: LinkVerifiedIdentityCommand) -> LoginIdentity:
        logger.info(
            "identity.link.persist.started",
            extra={
                "actor_id": str(command.actor_id),
                "provider": command.provider.value,
                "correlation_id": str(command.correlation_id),
            },
        )
        if command.provider is LoginIdentityProvider.EMAIL:
            logger.warning(
                "identity.link.persist.denied_provider",
                extra={
                    "actor_id": str(command.actor_id),
                    "provider": command.provider.value,
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise IdentityLinkRejectedError("Identity could not be linked.")
        if await self.user_statuses.get_status(user_id=command.actor_id) is not UserStatus.ACTIVE:
            logger.warning(
                "identity.link.persist.denied_inactive_user",
                extra={
                    "actor_id": str(command.actor_id),
                    "provider": command.provider.value,
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise IdentityLinkRejectedError("Identity could not be linked.")
        try:
            identity = LoginIdentity(
                id=self.identifiers.new(),
                user_id=command.actor_id,
                provider=command.provider,
                provider_subject=command.verified_provider_subject,
            )
        except ValueError as error:
            logger.warning(
                "identity.link.persist.invalid_subject",
                extra={
                    "actor_id": str(command.actor_id),
                    "provider": command.provider.value,
                    "error_type": type(error).__name__,
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise IdentityLinkRejectedError("Identity could not be linked.") from error
        linked = await self.identities.link(
            identity=identity,
            audit_event=AuditEvent(
                id=self.identifiers.new(),
                correlation_id=command.correlation_id,
                actor_id=command.actor_id,
                organization_id=None,
                action="identity.link",
                resource_type="login_identity",
                resource_id=str(identity.id),
                result="succeeded",
            ),
        )
        if not linked:
            logger.warning(
                "identity.link.persist.conflict",
                extra={
                    "actor_id": str(command.actor_id),
                    "provider": command.provider.value,
                    "identity_id": str(identity.id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise IdentityLinkRejectedError("Identity could not be linked.")
        logger.info(
            "identity.link.persist.completed",
            extra={
                "actor_id": str(command.actor_id),
                "provider": command.provider.value,
                "identity_id": str(identity.id),
                "correlation_id": str(command.correlation_id),
            },
        )
        return identity
