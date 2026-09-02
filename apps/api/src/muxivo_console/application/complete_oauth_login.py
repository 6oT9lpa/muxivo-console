"""Complete a one-time OAuth login only for an already linked Console identity."""

from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.create_browser_session import (
    CreateBrowserSession,
    CreateBrowserSessionCommand,
    IssuedBrowserSession,
)
from muxivo_console.application.ports import (
    Clock,
    OAuthIdentityProvider,
    OAuthLoginTransactionConsumer,
    OpaqueValueProtector,
    ProviderIdentityUserReader,
    SessionTokenHasher,
)
from muxivo_console.domain.identity import LoginIdentityProvider
from muxivo_console.domain.sessions import SessionAssuranceLevel


class OAuthLoginCompletionRejectedError(PermissionError):
    """Publicly safe callback failure without account-enumeration detail."""


@dataclass(slots=True)
class CompleteOAuthLogin:
    clock: Clock
    token_hasher: SessionTokenHasher
    secrets: OpaqueValueProtector
    transactions: OAuthLoginTransactionConsumer
    provider_client: OAuthIdentityProvider
    identities: ProviderIdentityUserReader
    sessions: CreateBrowserSession

    async def execute(
        self,
        *,
        provider: LoginIdentityProvider,
        state: str,
        authorization_code: str,
        correlation_id: UUID,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> IssuedBrowserSession:
        if provider is LoginIdentityProvider.EMAIL or not state or not authorization_code:
            raise OAuthLoginCompletionRejectedError("OAuth login could not be completed.")
        transaction = await self.transactions.consume(
            state_hash=self.token_hasher.hash(state), consumed_at=self.clock.now()
        )
        if transaction is None or transaction.provider is not provider:
            raise OAuthLoginCompletionRejectedError("OAuth login could not be completed.")
        try:
            provider_subject = await self.provider_client.resolve_subject(
                authorization_code=authorization_code,
                code_verifier=self.secrets.decrypt(transaction.code_verifier_ciphertext),
            )
            user_id = await self.identities.find_user_id(
                provider=provider, provider_subject=provider_subject
            )
            if user_id is None:
                raise ValueError("Provider identity is not linked.")
            return await self.sessions.execute(
                CreateBrowserSessionCommand(
                    user_id=user_id,
                    correlation_id=correlation_id,
                    assurance_level=SessionAssuranceLevel.RECENT_AUTHENTICATION,
                    client_ip=client_ip,
                    user_agent=user_agent,
                )
            )
        except Exception as error:
            raise OAuthLoginCompletionRejectedError(
                "OAuth login could not be completed."
            ) from error
