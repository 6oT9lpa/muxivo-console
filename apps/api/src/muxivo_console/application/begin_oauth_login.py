"""Start provider-neutral OAuth browser login with PKCE and one-time state."""

import base64
import hashlib
from dataclasses import dataclass, field
from datetime import timedelta
from uuid import UUID

from muxivo_console.application.ports import (
    Clock,
    IdentifierGenerator,
    OAuthLoginTransactionWriter,
    OpaqueSessionTokenIssuer,
    OpaqueValueProtector,
    SessionTokenHasher,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import LoginIdentityProvider
from muxivo_console.domain.oauth_login import OAuthLoginTransaction


class OAuthLoginStartRejectedError(PermissionError):
    """Publicly safe failure for OAuth login initialization."""


@dataclass(frozen=True, slots=True)
class StartedOAuthLogin:
    state: str = field(repr=False)
    code_challenge: str
    expires_in_seconds: int


@dataclass(slots=True)
class BeginOAuthLogin:
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
        if provider is LoginIdentityProvider.EMAIL:
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
            raise OAuthLoginStartRejectedError("OAuth login could not be started.")
        challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        return StartedOAuthLogin(
            state=state,
            code_challenge=challenge.rstrip(b"=").decode(),
            expires_in_seconds=int(self.lifetime.total_seconds()),
        )
