"""Use case for completing one-time OAuth login for a linked identity."""

import logging
from dataclasses import dataclass
from uuid import UUID

from muxivo_console.application.create_browser_session import (
    CreateBrowserSession,
    CreateBrowserSessionCommand,
    IssuedBrowserSession,
)
from muxivo_console.application.oauth_login_completion_error import (
    OAuthLoginCompletionRejectedError,
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

logger = logging.getLogger("muxivo_console.application.complete_oauth_login")


@dataclass(slots=True)
class CompleteOAuthLogin:
    """Resolve a provider subject and issue a recent-authentication session."""

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
        logger.info(
            "auth.oauth_login.complete.started",
            extra={
                "provider": provider.value,
                "correlation_id": str(correlation_id),
                "has_state": bool(state),
                "has_authorization_code": bool(authorization_code),
            },
        )
        if provider is LoginIdentityProvider.EMAIL or not state or not authorization_code:
            logger.warning(
                "auth.oauth_login.complete.invalid_callback",
                extra={"provider": provider.value, "correlation_id": str(correlation_id)},
            )
            raise OAuthLoginCompletionRejectedError("OAuth login could not be completed.")
        transaction = await self.transactions.consume(
            state_hash=self.token_hasher.hash(state), consumed_at=self.clock.now()
        )
        if transaction is None or transaction.provider is not provider:
            logger.warning(
                "auth.oauth_login.complete.invalid_transaction",
                extra={"provider": provider.value, "correlation_id": str(correlation_id)},
            )
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
            session = await self.sessions.execute(
                CreateBrowserSessionCommand(
                    user_id=user_id,
                    correlation_id=correlation_id,
                    assurance_level=SessionAssuranceLevel.RECENT_AUTHENTICATION,
                    client_ip=client_ip,
                    user_agent=user_agent,
                )
            )
            logger.info(
                "auth.oauth_login.complete.completed",
                extra={
                    "provider": provider.value,
                    "transaction_id": str(transaction.id),
                    "user_id": str(user_id),
                    "session_id": str(session.id),
                    "correlation_id": str(correlation_id),
                },
            )
            return session
        except Exception as error:
            logger.warning(
                "auth.oauth_login.complete.failed",
                extra={
                    "provider": provider.value,
                    "transaction_id": str(transaction.id),
                    "error_type": type(error).__name__,
                    "correlation_id": str(correlation_id),
                },
            )
            raise OAuthLoginCompletionRejectedError(
                "OAuth login could not be completed."
            ) from error
