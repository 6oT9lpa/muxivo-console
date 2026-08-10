"""Transactional persistence adapters for organization role management."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.organizations import OrganizationMember, OrganizationRole
from muxivo_console.infrastructure.persistence.models import (
    AuditEventRecord,
    OrganizationMembershipRecord,
    UserRecord,
)


class SqlAlchemyOrganizationMemberLookup:
    """Resolve one non-secret member projection inside exactly one tenant."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def find_for_organization(
        self, *, organization_id: UUID, membership_id: UUID
    ) -> OrganizationMember | None:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(OrganizationMembershipRecord, UserRecord.display_name)
                    .join(UserRecord, UserRecord.id == OrganizationMembershipRecord.user_id)
                    .where(
                        OrganizationMembershipRecord.organization_id == organization_id,
                        OrganizationMembershipRecord.id == membership_id,
                    )
                )
            ).one_or_none()
        if row is None:
            return None
        membership, display_name = row
        try:
            return OrganizationMember(
                membership_id=membership.id,
                user_id=membership.user_id,
                display_name=display_name,
                role=OrganizationRole(membership.role),
            )
        except ValueError:
            return None


class SqlAlchemyOrganizationMemberRoleWriter:
    """Lock actor and target memberships, then persist role + audit atomically."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def change_role(
        self,
        *,
        organization_id: UUID,
        actor_membership_id: UUID,
        actor_id: UUID,
        expected_actor_role: OrganizationRole,
        membership_id: UUID,
        target_user_id: UUID,
        expected_role: OrganizationRole,
        new_role: OrganizationRole,
        audit_event: AuditEvent,
    ) -> bool:
        if actor_membership_id == membership_id:
            return False
        async with self._session_factory() as session:
            async with session.begin():
                actor = (
                    await session.execute(
                        select(OrganizationMembershipRecord)
                        .where(
                            OrganizationMembershipRecord.id == actor_membership_id,
                            OrganizationMembershipRecord.organization_id == organization_id,
                            OrganizationMembershipRecord.user_id == actor_id,
                        )
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if actor is None or actor.role != expected_actor_role.value:
                    return False

                target = (
                    await session.execute(
                        select(OrganizationMembershipRecord)
                        .where(
                            OrganizationMembershipRecord.id == membership_id,
                            OrganizationMembershipRecord.organization_id == organization_id,
                            OrganizationMembershipRecord.user_id == target_user_id,
                        )
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if target is None or target.role != expected_role.value:
                    return False

                target.role = new_role.value
                session.add(
                    AuditEventRecord(
                        id=audit_event.id,
                        correlation_id=audit_event.correlation_id,
                        actor_id=audit_event.actor_id,
                        organization_id=audit_event.organization_id,
                        action=audit_event.action,
                        resource_type=audit_event.resource_type,
                        resource_id=audit_event.resource_id,
                        result=audit_event.result,
                    )
                )
                await session.flush()
        return True
