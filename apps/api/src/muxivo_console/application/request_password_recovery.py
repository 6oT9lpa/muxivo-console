"""Start an anti-enumeration password recovery flow."""

import logging
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from muxivo_console.application.ports import (
    Clock,
    EmailAddressNormalizer,
    EmailLookupHasher,
    EmailPasswordAccountReader,
    IdentifierGenerator,
    OpaqueSessionTokenIssuer,
    PasswordRecoveryNotifier,
    PasswordRecoveryTransactionWriter,
    SessionTokenHasher,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import UserStatus
from muxivo_console.domain.password_recovery import PasswordRecoveryTransaction

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RequestPasswordRecoveryCommand:
    email: str
    correlation_id: UUID


@dataclass(slots=True)
class RequestPasswordRecovery:
    identifiers: IdentifierGenerator
    clock: Clock
    email_normalizer: EmailAddressNormalizer
    email_lookup_hasher: EmailLookupHasher
    token_issuer: OpaqueSessionTokenIssuer
    token_hasher: SessionTokenHasher
    accounts: EmailPasswordAccountReader
    transactions: PasswordRecoveryTransactionWriter
    notifier: PasswordRecoveryNotifier
    lifetime: timedelta = timedelta(minutes=30)

    async def execute(self, command: RequestPasswordRecoveryCommand) -> None:
        logger.info(
            "password.recovery.request.started",
            extra={"correlation_id": str(command.correlation_id)},
        )
        raw_token = self.token_issuer.issue()
        token_hash = self.token_hasher.hash(raw_token)
        try:
            normalized_email = self.email_normalizer.normalize(command.email)
        except ValueError:
            logger.warning(
                "password.recovery.request.invalid_email",
                extra={"correlation_id": str(command.correlation_id)},
            )
            return
        account = await self.accounts.find_by_email_lookup_hash(
            email_lookup_hash=self.email_lookup_hasher.lookup_hash(normalized_email)
        )
        if account is None or account.status is not UserStatus.ACTIVE:
            logger.info(
                "password.recovery.request.completed_without_delivery",
                extra={"correlation_id": str(command.correlation_id)},
            )
            return

        now = self.clock.now()
        transaction = PasswordRecoveryTransaction(
            id=self.identifiers.new(),
            user_id=account.user_id,
            token_hash=token_hash,
            expires_at=now + self.lifetime,
        )
        created = await self.transactions.create(
            transaction=transaction,
            audit_event=AuditEvent(
                id=self.identifiers.new(),
                correlation_id=command.correlation_id,
                actor_id=account.user_id,
                organization_id=None,
                action="auth.password_recovery_requested",
                resource_type="user",
                resource_id=str(account.user_id),
                result="succeeded",
            ),
        )
        if not created:
            logger.warning(
                "password.recovery.request.conflict",
                extra={
                    "user_id": str(account.user_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            return
        try:
            await self.notifier.send(
                user_id=account.user_id,
                recipient_email=normalized_email,
                raw_token=raw_token,
                expires_at=transaction.expires_at,
                correlation_id=command.correlation_id,
            )
        except Exception as error:
            logger.error(
                "password.recovery.request.delivery_failed",
                extra={
                    "user_id": str(account.user_id),
                    "error_type": type(error).__name__,
                    "correlation_id": str(command.correlation_id),
                },
            )
            return
        logger.info(
            "password.recovery.request.completed",
            extra={
                "user_id": str(account.user_id),
                "correlation_id": str(command.correlation_id),
            },
        )
