"""Consume OAuth state once and link the provider subject resolved by a trusted adapter."""

from dataclasses import dataclass
from uuid import UUID

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
from muxivo_console.domain.identity import LoginIdentity, LoginIdentityProvider


class IdentityLinkCompletionRejectedError(PermissionError):
    """Publicly safe OAuth callback failure; no state/provider detail is exposed."""


@dataclass(frozen=True, slots=True)
class CompleteIdentityLinkCommand:
    provider: LoginIdentityProvider
    state: str
    authorization_code: str
    correlation_id: UUID


@dataclass(slots=True)
class CompleteIdentityLink:
    clock: Clock
    token_hasher: SessionTokenHasher
    secrets: OpaqueValueProtector
    transactions: IdentityLinkTransactionConsumer
    provider_client: OAuthIdentityProvider
    linker: LinkVerifiedIdentity

    async def execute(self, command: CompleteIdentityLinkCommand) -> LoginIdentity:
        if not command.state or not command.authorization_code:
            raise IdentityLinkCompletionRejectedError("Identity link could not be completed.")
        transaction = await self.transactions.consume(
            state_hash=self.token_hasher.hash(command.state), consumed_at=self.clock.now()
        )
        if transaction is None or transaction.provider is not command.provider:
            raise IdentityLinkCompletionRejectedError("Identity link could not be completed.")
        try:
            verifier = self.secrets.decrypt(transaction.code_verifier_ciphertext)
            provider_subject = await self.provider_client.resolve_subject(
                authorization_code=command.authorization_code,
                code_verifier=verifier,
            )
            return await self.linker.execute(
                LinkVerifiedIdentityCommand(
                    actor_id=transaction.user_id,
                    provider=transaction.provider,
                    verified_provider_subject=provider_subject,
                    correlation_id=command.correlation_id,
                )
            )
        except (IdentityLinkRejectedError, ValueError) as error:
            raise IdentityLinkCompletionRejectedError(
                "Identity link could not be completed."
            ) from error
