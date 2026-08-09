"""Create a one-time OAuth state and PKCE challenge for an external identity link."""

import base64
import hashlib
from dataclasses import dataclass, field
from datetime import timedelta
from uuid import UUID

from muxivo_console.application.ports import (
    Clock,
    IdentifierGenerator,
    IdentityLinkTransactionWriter,
    OpaqueSessionTokenIssuer,
    OpaqueValueProtector,
    SessionTokenHasher,
    UserStatusReader,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import LoginIdentityProvider, UserStatus
from muxivo_console.domain.identity_linking import IdentityLinkTransaction


class IdentityLinkStartRejectedError(PermissionError):
    """Safe public failure for an unusable OAuth link initiation."""


@dataclass(frozen=True, slots=True)
class BeginIdentityLinkCommand:
    actor_id: UUID
    provider: LoginIdentityProvider
    correlation_id: UUID


@dataclass(frozen=True, slots=True)
class StartedIdentityLink:
    state: str = field(repr=False)
    code_challenge: str
    expires_in_seconds: int


@dataclass(slots=True)
class BeginIdentityLink:
    identifiers: IdentifierGenerator
    clock: Clock
    user_statuses: UserStatusReader
    token_issuer: OpaqueSessionTokenIssuer
    token_hasher: SessionTokenHasher
    secrets: OpaqueValueProtector
    transactions: IdentityLinkTransactionWriter
    lifetime: timedelta = timedelta(minutes=10)

    async def execute(self, command: BeginIdentityLinkCommand) -> StartedIdentityLink:
        if command.provider is LoginIdentityProvider.EMAIL:
            raise IdentityLinkStartRejectedError("Identity link could not be started.")
        if await self.user_statuses.get_status(user_id=command.actor_id) is not UserStatus.ACTIVE:
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
            raise IdentityLinkStartRejectedError("Identity link could not be started.")
        challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        return StartedIdentityLink(
            state=state,
            code_challenge=challenge.rstrip(b"=").decode(),
            expires_in_seconds=int(self.lifetime.total_seconds()),
        )
