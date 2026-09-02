"""Use case for consuming OAuth state and linking a verified provider subject."""

import logging
from dataclasses import dataclass

from muxivo_console.application.complete_identity_link_command import CompleteIdentityLinkCommand
from muxivo_console.application.identity_link_completion_error import (
    IdentityLinkCompletionRejectedError,
)
from muxivo_console.application.link_verified_identity import (
    IdentityLinkRejectedError,
    LinkVerifiedIdentity,
    LinkVerifiedIdentityCommand,
)
from muxivo_console.application.ports import (
    Clock,
    IdentityLinkTransactionConsumer,
    OAuthIdentityProvider,
    OpaqueValueProtector,
    SessionTokenHasher,
)
from muxivo_console.domain.identity import LoginIdentity

logger = logging.getLogger("muxivo_console.application.complete_identity_link")


@dataclass(slots=True)
class CompleteIdentityLink:
    """Consume one-time state and delegate subject linking to a trusted adapter."""

    clock: Clock
    token_hasher: SessionTokenHasher
    secrets: OpaqueValueProtector
    transactions: IdentityLinkTransactionConsumer
    provider_client: OAuthIdentityProvider
    linker: LinkVerifiedIdentity

    async def execute(self, command: CompleteIdentityLinkCommand) -> LoginIdentity:
        logger.info(
            "identity.link.complete.started",
            extra={
                "provider": command.provider.value,
                "correlation_id": str(command.correlation_id),
                "has_state": bool(command.state),
                "has_authorization_code": bool(command.authorization_code),
            },
        )
        if not command.state or not command.authorization_code:
            logger.warning(
                "identity.link.complete.invalid_callback",
                extra={
                    "provider": command.provider.value,
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise IdentityLinkCompletionRejectedError("Identity link could not be completed.")
        transaction = await self.transactions.consume(
            state_hash=self.token_hasher.hash(command.state), consumed_at=self.clock.now()
        )
        if transaction is None or transaction.provider is not command.provider:
            logger.warning(
                "identity.link.complete.invalid_transaction",
                extra={
                    "provider": command.provider.value,
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise IdentityLinkCompletionRejectedError("Identity link could not be completed.")
        try:
            verifier = self.secrets.decrypt(transaction.code_verifier_ciphertext)
            provider_subject = await self.provider_client.resolve_subject(
                authorization_code=command.authorization_code,
                code_verifier=verifier,
            )
            identity = await self.linker.execute(
                LinkVerifiedIdentityCommand(
                    actor_id=transaction.user_id,
                    provider=transaction.provider,
                    verified_provider_subject=provider_subject,
                    correlation_id=command.correlation_id,
                )
            )
            logger.info(
                "identity.link.complete.completed",
                extra={
                    "provider": command.provider.value,
                    "transaction_id": str(transaction.id),
                    "identity_id": str(identity.id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            return identity
        except (IdentityLinkRejectedError, ValueError) as error:
            logger.warning(
                "identity.link.complete.failed",
                extra={
                    "provider": command.provider.value,
                    "transaction_id": str(transaction.id),
                    "error_type": type(error).__name__,
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise IdentityLinkCompletionRejectedError(
                "Identity link could not be completed."
            ) from error
