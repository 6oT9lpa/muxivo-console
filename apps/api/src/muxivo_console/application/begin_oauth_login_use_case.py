"""Use case for starting provider-neutral OAuth login with PKCE."""

import base64
import hashlib
import logging
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from muxivo_console.application.oauth_login_start_error import OAuthLoginStartRejectedError
from muxivo_console.application.ports import (
    Clock,
    IdentifierGenerator,
    OAuthLoginTransactionWriter,
    OpaqueSessionTokenIssuer,
    OpaqueValueProtector,
    SessionTokenHasher,
)
from muxivo_console.application.started_oauth_login import StartedOAuthLogin
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import LoginIdentityProvider
from muxivo_console.domain.oauth_login import OAuthLoginTransaction

logger = logging.getLogger("muxivo_console.application.begin_oauth_login")


@dataclass(slots=True)
class BeginOAuthLogin:
    """Create a protected OAuth transaction for a supported external provider."""

    identifiers: IdentifierGenerator
    clock: Clock
    token_issuer: OpaqueSessionTokenIssuer
    token_hasher: SessionTokenHasher
    secrets: OpaqueValueProtector
    transactions: OAuthLoginTransactionWriter
    lifetime: timedelta = timedelta(minutes=10)

    async def execute(
        self, *, provider: LoginIdentityProvider, correlation_id: UUID
    ) -> StartedOAuthLogin:
        logger.info(
            "auth.oauth_login.start.started",
            extra={"provider": provider.value, "correlation_id": str(correlation_id)},
        )
        if provider is LoginIdentityProvider.EMAIL:
            logger.warning(
                "auth.oauth_login.start.denied_provider",
                extra={"provider": provider.value, "correlation_id": str(correlation_id)},
            )
            raise OAuthLoginStartRejectedError("OAuth login could not be started.")
        state, code_verifier = self.token_issuer.issue(), self.token_issuer.issue()
        transaction = OAuthLoginTransaction(
            id=self.identifiers.new(),
            provider=provider,
            state_hash=self.token_hasher.hash(state),
            code_verifier_ciphertext=self.secrets.encrypt(code_verifier),
            expires_at=self.clock.now() + self.lifetime,
        )
        if not await self.transactions.create(
            transaction=transaction,
            audit_event=AuditEvent(
                id=self.identifiers.new(),
                correlation_id=correlation_id,
                actor_id=None,
                organization_id=None,
                action="auth.oauth_login_started",
                resource_type="oauth_login_transaction",
                resource_id=str(transaction.id),
                result="succeeded",
            ),
        ):
            logger.warning(
                "auth.oauth_login.start.persistence_failed",
                extra={
                    "provider": provider.value,
                    "transaction_id": str(transaction.id),
                    "correlation_id": str(correlation_id),
                },
            )
            raise OAuthLoginStartRejectedError("OAuth login could not be started.")
        challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        logger.info(
            "auth.oauth_login.start.completed",
            extra={
                "provider": provider.value,
                "transaction_id": str(transaction.id),
                "correlation_id": str(correlation_id),
            },
        )
        return StartedOAuthLogin(
            state=state,
            code_challenge=challenge.rstrip(b"=").decode(),
            expires_in_seconds=int(self.lifetime.total_seconds()),
        )
