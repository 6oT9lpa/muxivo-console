"""SQLAlchemy persistence for first-party password recovery transactions."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.password_recovery import PasswordRecoveryTransaction
from muxivo_console.infrastructure.persistence.models import (
    AuditEventRecord,
    AuthSessionRecord,
    PasswordCredentialRecord,
    PasswordRecoveryTransactionRecord,
)


class SqlAlchemyPasswordRecoveryRepository:
    """Store and consume one-time password recovery tokens as hashes only."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def create(
        self, *, transaction: PasswordRecoveryTransaction, audit_event: AuditEvent
    ) -> bool:
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    session.add_all(
                        (
                            PasswordRecoveryTransactionRecord(
                                id=transaction.id,
                                user_id=transaction.user_id,
                                token_hash=transaction.token_hash,
                                expires_at=transaction.expires_at,
                                consumed_at=transaction.consumed_at,
                            ),
                            AuditEventRecord(
                                id=audit_event.id,
                                correlation_id=audit_event.correlation_id,
                                actor_id=audit_event.actor_id,
                                organization_id=audit_event.organization_id,
                                action=audit_event.action,
                                resource_type=audit_event.resource_type,
                                resource_id=audit_event.resource_id,
                                result=audit_event.result,
                            ),
                        )
                    )
                    await session.flush()
        except IntegrityError:
            return False
        return True

    async def complete(
        self,
        *,
        token_hash: str,
        password_hash: str,
        completed_at,
        audit_id,
        correlation_id,
    ) -> UUID | None:
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    recovery_record = (
                        await session.execute(
                            update(PasswordRecoveryTransactionRecord)
                            .where(
                                PasswordRecoveryTransactionRecord.token_hash == token_hash,
                                PasswordRecoveryTransactionRecord.consumed_at.is_(None),
                                PasswordRecoveryTransactionRecord.expires_at > completed_at,
                            )
                            .values(consumed_at=completed_at)
                            .returning(PasswordRecoveryTransactionRecord)
                        )
                    ).scalar_one_or_none()
                    if recovery_record is None:
                        return None
                    password_result = await session.execute(
                        update(PasswordCredentialRecord)
                        .where(PasswordCredentialRecord.user_id == recovery_record.user_id)
                        .values(
                            password_hash=password_hash,
                            password_changed_at=completed_at,
                            failed_attempts=0,
                            locked_until=None,
                        )
                    )
                    if password_result.rowcount != 1:
                        return None
                    await session.execute(
                        update(AuthSessionRecord)
                        .where(
                            AuthSessionRecord.user_id == recovery_record.user_id,
                            AuthSessionRecord.revoked_at.is_(None),
                            AuthSessionRecord.expires_at > completed_at,
                        )
                        .values(revoked_at=completed_at)
                    )
                    session.add(
                        AuditEventRecord(
                            id=audit_id,
                            correlation_id=correlation_id,
                            actor_id=recovery_record.user_id,
                            organization_id=None,
                            action="auth.password_recovered",
                            resource_type="user",
                            resource_id=str(recovery_record.user_id),
                            result="succeeded",
                        )
                    )
                    await session.flush()
        except IntegrityError:
            return None
        return recovery_record.user_id
