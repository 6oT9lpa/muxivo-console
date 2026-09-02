"""SQLAlchemy reader for secret-free organization invitation projections."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.domain.organization_invitations import OrganizationInvitation
from muxivo_console.infrastructure.persistence.models import (
    OrganizationInvitationRecord,
    OrganizationInvitationScopeRecord,
)
from muxivo_console.infrastructure.persistence.organization_invitation_mapping import (
    invitation_from_records,
)


class SqlAlchemyOrganizationInvitationReader:
    """Read invitation metadata without selecting encrypted e-mail ciphertext."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def list_for_organization(
        self, *, organization_id: UUID
    ) -> tuple[OrganizationInvitation, ...]:
        statement = (
            select(OrganizationInvitationRecord)
            .where(OrganizationInvitationRecord.organization_id == organization_id)
            .order_by(
                OrganizationInvitationRecord.created_at.desc(),
                OrganizationInvitationRecord.id,
            )
        )
        async with self._session_factory() as session:
            records = (await session.execute(statement)).scalars().all()
            scopes = await _scopes_for_invitations(session, [record.id for record in records])
        return tuple(
            invitation
            for record in records
            if (invitation := invitation_from_records(record, scopes.get(record.id, ())))
            is not None
        )

    async def find_for_organization(
        self, *, organization_id: UUID, invitation_id: UUID
    ) -> OrganizationInvitation | None:
        statement = select(OrganizationInvitationRecord).where(
            OrganizationInvitationRecord.organization_id == organization_id,
            OrganizationInvitationRecord.id == invitation_id,
        )
        async with self._session_factory() as session:
            record = (await session.execute(statement)).scalar_one_or_none()
            if record is None:
                return None
            scopes = await _scopes_for_invitations(session, [record.id])
        return invitation_from_records(record, scopes.get(record.id, ()))

    async def find_pending_by_token_hash(
        self, *, token_hash: str, now
    ) -> OrganizationInvitation | None:
        statement = select(OrganizationInvitationRecord).where(
            OrganizationInvitationRecord.token_hash == token_hash,
            OrganizationInvitationRecord.accepted_at.is_(None),
            OrganizationInvitationRecord.revoked_at.is_(None),
            OrganizationInvitationRecord.expires_at > now,
        )
        async with self._session_factory() as session:
            record = (await session.execute(statement)).scalar_one_or_none()
            if record is None:
                return None
            scopes = await _scopes_for_invitations(session, [record.id])
        return invitation_from_records(record, scopes.get(record.id, ()))


async def _scopes_for_invitations(
    session: AsyncSession, invitation_ids: list[UUID]
) -> dict[UUID, tuple[OrganizationInvitationScopeRecord, ...]]:
    if not invitation_ids:
        return {}
    result = await session.execute(
        select(OrganizationInvitationScopeRecord).where(
            OrganizationInvitationScopeRecord.invitation_id.in_(invitation_ids)
        )
    )
    grouped: dict[UUID, list[OrganizationInvitationScopeRecord]] = {}
    for scope in result.scalars().all():
        grouped.setdefault(scope.invitation_id, []).append(scope)
    return {invitation_id: tuple(scopes) for invitation_id, scopes in grouped.items()}
