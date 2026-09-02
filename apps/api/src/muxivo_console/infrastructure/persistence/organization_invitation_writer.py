"""Transactional SQLAlchemy writer for organization invitation lifecycle changes."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.organization_invitations import (
    OrganizationInvitation,
    OrganizationInvitationDeliveryStatus,
)
from muxivo_console.domain.organizations import OrganizationMembership
from muxivo_console.infrastructure.persistence.models import (
    AuditEventRecord,
    MembershipResourceScopeRecord,
    OrganizationInvitationRecord,
    OrganizationInvitationScopeRecord,
    OrganizationMembershipRecord,
)


class SqlAlchemyOrganizationInvitationWriter:
    """Keep invitation acceptance and membership creation in one transaction."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def create(
        self, *, invitation: OrganizationInvitation, audit_event: AuditEvent
    ) -> bool:
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    session.add(
                        OrganizationInvitationRecord(
                            id=invitation.id,
                            organization_id=invitation.organization_id,
                            invited_by_user_id=invitation.invited_by_user_id,
                            email_ciphertext=invitation.email_ciphertext,
                            email_lookup_hash=invitation.email_lookup_hash,
                            email_hint=invitation.email_hint,
                            token_hash=invitation.token_hash,
                            role=invitation.role.value,
                            delivery_status=(
                                invitation.delivery_status.value
                                if invitation.delivery_status is not None
                                else None
                            ),
                            expires_at=invitation.expires_at,
                            created_at=invitation.created_at,
                        )
                    )
                    await session.flush()
                    session.add_all(
                        tuple(
                            _invitation_scope_record(invitation.id, scope)
                            for scope in invitation.resource_scopes
                        )
                        + (_audit_record(audit_event),)
                    )
                    await session.flush()
        except IntegrityError:
            return False
        return True

    async def update_delivery_status(
        self,
        *,
        invitation_id: UUID,
        organization_id: UUID,
        delivery_status: OrganizationInvitationDeliveryStatus,
    ) -> bool:
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    update(OrganizationInvitationRecord)
                    .where(
                        OrganizationInvitationRecord.id == invitation_id,
                        OrganizationInvitationRecord.organization_id == organization_id,
                    )
                    .values(delivery_status=delivery_status.value)
                )
        return result.rowcount == 1

    async def accept(
        self,
        *,
        invitation: OrganizationInvitation,
        membership: OrganizationMembership,
        accepted_at,
        audit_event: AuditEvent,
    ) -> bool:
        if membership.id is None:
            raise ValueError("Invitation acceptance requires a membership identifier.")
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    result = await session.execute(
                        update(OrganizationInvitationRecord)
                        .where(
                            OrganizationInvitationRecord.id == invitation.id,
                            OrganizationInvitationRecord.organization_id
                            == invitation.organization_id,
                            OrganizationInvitationRecord.accepted_at.is_(None),
                            OrganizationInvitationRecord.revoked_at.is_(None),
                            OrganizationInvitationRecord.expires_at > accepted_at,
                        )
                        .values(accepted_at=accepted_at)
                    )
                    if result.rowcount != 1:
                        return False
                    session.add(
                        OrganizationMembershipRecord(
                            id=membership.id,
                            organization_id=membership.organization_id,
                            user_id=membership.actor_id,
                            role=membership.role.value,
                        )
                    )
                    await session.flush()
                    session.add_all(
                        tuple(
                            _membership_scope_record(membership.id, scope)
                            for scope in membership.resource_scopes
                        )
                        + (_audit_record(audit_event),)
                    )
                    await session.flush()
        except IntegrityError:
            return False
        return True

    async def revoke(
        self, *, invitation_id: UUID, organization_id: UUID, revoked_at, audit_event: AuditEvent
    ) -> bool:
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    result = await session.execute(
                        update(OrganizationInvitationRecord)
                        .where(
                            OrganizationInvitationRecord.id == invitation_id,
                            OrganizationInvitationRecord.organization_id == organization_id,
                            OrganizationInvitationRecord.accepted_at.is_(None),
                            OrganizationInvitationRecord.revoked_at.is_(None),
                            OrganizationInvitationRecord.expires_at > revoked_at,
                        )
                        .values(revoked_at=revoked_at)
                    )
                    if result.rowcount != 1:
                        return False
                    session.add(_audit_record(audit_event))
                    await session.flush()
        except IntegrityError:
            return False
        return True


def _invitation_scope_record(
    invitation_id: UUID, scope
) -> OrganizationInvitationScopeRecord:
    if scope.id is None:
        raise ValueError("Invitation resource scopes require server-generated identifiers.")
    return OrganizationInvitationScopeRecord(
        id=scope.id,
        invitation_id=invitation_id,
        resource=scope.resource.value,
        action=scope.action.value,
    )


def _membership_scope_record(
    membership_id: UUID, scope
) -> MembershipResourceScopeRecord:
    if scope.id is None:
        raise ValueError("Membership resource scopes require server-generated identifiers.")
    return MembershipResourceScopeRecord(
        id=scope.id,
        membership_id=membership_id,
        resource=scope.resource.value,
        action=scope.action.value,
    )


def _audit_record(audit_event: AuditEvent) -> AuditEventRecord:
    return AuditEventRecord(
        id=audit_event.id,
        correlation_id=audit_event.correlation_id,
        actor_id=audit_event.actor_id,
        organization_id=audit_event.organization_id,
        action=audit_event.action,
        resource_type=audit_event.resource_type,
        resource_id=audit_event.resource_id,
        result=audit_event.result,
    )
