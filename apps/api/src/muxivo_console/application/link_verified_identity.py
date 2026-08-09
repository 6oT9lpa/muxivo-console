"""Link an externally verified provider subject to an active Console user."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.ports import (
    IdentifierGenerator,
    LoginIdentityLinkWriter,
    UserStatusReader,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import LoginIdentity, LoginIdentityProvider, UserStatus


class IdentityLinkRejectedError(PermissionError):
    """Publicly safe failure for inactive, invalid, or already-linked identities."""


@dataclass(frozen=True, slots=True)
class LinkVerifiedIdentityCommand:
    actor_id: UUID
    provider: LoginIdentityProvider
    verified_provider_subject: str
    correlation_id: UUID


@dataclass(slots=True)
class LinkVerifiedIdentity:
    identifiers: IdentifierGenerator
    user_statuses: UserStatusReader
    identities: LoginIdentityLinkWriter

    async def execute(self, command: LinkVerifiedIdentityCommand) -> LoginIdentity:
        if command.provider is LoginIdentityProvider.EMAIL:
            raise IdentityLinkRejectedError("Identity could not be linked.")
        if await self.user_statuses.get_status(user_id=command.actor_id) is not UserStatus.ACTIVE:
            raise IdentityLinkRejectedError("Identity could not be linked.")
        try:
            identity = LoginIdentity(
                id=self.identifiers.new(),
                user_id=command.actor_id,
                provider=command.provider,
                provider_subject=command.verified_provider_subject,
            )
        except ValueError as error:
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
            raise IdentityLinkRejectedError("Identity could not be linked.")
        return identity
