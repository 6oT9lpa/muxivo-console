"""Use case for starting a one-time OAuth identity link."""

import base64
import hashlib
import logging
from dataclasses import dataclass
from datetime import timedelta

from muxivo_console.application.begin_identity_link_command import BeginIdentityLinkCommand
from muxivo_console.application.identity_link_start_error import IdentityLinkStartRejectedError
from muxivo_console.application.ports import (
    Clock,
    IdentifierGenerator,
    IdentityLinkTransactionWriter,
    OpaqueSessionTokenIssuer,
    OpaqueValueProtector,
    SessionTokenHasher,
    UserStatusReader,
)
from muxivo_console.application.started_identity_link import StartedIdentityLink
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import LoginIdentityProvider, UserStatus
from muxivo_console.domain.identity_linking import IdentityLinkTransaction

logger = logging.getLogger("muxivo_console.application.begin_identity_link")


@dataclass(slots=True)
class BeginIdentityLink:
    """Create a protected OAuth transaction for an active Console user."""

    identifiers: IdentifierGenerator
    clock: Clock
    user_statuses: UserStatusReader
    token_issuer: OpaqueSessionTokenIssuer
    token_hasher: SessionTokenHasher
    secrets: OpaqueValueProtector
    transactions: IdentityLinkTransactionWriter
    lifetime: timedelta = timedelta(minutes=10)

    async def execute(self, command: BeginIdentityLinkCommand) -> StartedIdentityLink:
        logger.info(
            "identity.link.start.started",
            extra={
                "actor_id": str(command.actor_id),
                "provider": command.provider.value,
                "correlation_id": str(command.correlation_id),
            },
        )
        if command.provider is LoginIdentityProvider.EMAIL:
            logger.warning(
                "identity.link.start.denied_provider",
                extra={
                    "actor_id": str(command.actor_id),
                    "provider": command.provider.value,
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise IdentityLinkStartRejectedError("Identity link could not be started.")
        if await self.user_statuses.get_status(user_id=command.actor_id) is not UserStatus.ACTIVE:
            logger.warning(
                "identity.link.start.denied_inactive_user",
                extra={
                    "actor_id": str(command.actor_id),
                    "provider": command.provider.value,
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise IdentityLinkStartRejectedError("Identity link could not be started.")

        now = self.clock.now()
        state = self.token_issuer.issue()
        code_verifier = self.token_issuer.issue()
        transaction = IdentityLinkTransaction(
            id=self.identifiers.new(),
            user_id=command.actor_id,
            provider=command.provider,
            state_hash=self.token_hasher.hash(state),
            code_verifier_ciphertext=self.secrets.encrypt(code_verifier),
            expires_at=now + self.lifetime,
        )
        created = await self.transactions.create(
            transaction=transaction,
            audit_event=AuditEvent(
                id=self.identifiers.new(),
                correlation_id=command.correlation_id,
                actor_id=command.actor_id,
                organization_id=None,
                action="identity.link_started",
                resource_type="identity_link_transaction",
                resource_id=str(transaction.id),
                result="succeeded",
            ),
        )
        if not created:
            logger.warning(
                "identity.link.start.persistence_failed",
                extra={
                    "actor_id": str(command.actor_id),
                    "provider": command.provider.value,
                    "transaction_id": str(transaction.id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise IdentityLinkStartRejectedError("Identity link could not be started.")
        challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        logger.info(
            "identity.link.start.completed",
            extra={
                "actor_id": str(command.actor_id),
                "provider": command.provider.value,
                "transaction_id": str(transaction.id),
                "correlation_id": str(command.correlation_id),
            },
        )
        return StartedIdentityLink(
            state=state,
            code_challenge=challenge.rstrip(b"=").decode(),
            expires_in_seconds=int(self.lifetime.total_seconds()),
        )
