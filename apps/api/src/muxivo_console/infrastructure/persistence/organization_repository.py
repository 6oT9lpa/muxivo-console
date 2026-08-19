"""SQLAlchemy adapters for Console-owned organization creation and user status."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.authorization import AuthorizationAction, AuthorizationResource
from muxivo_console.domain.identity import UserStatus
from muxivo_console.domain.organizations import (
    MembershipResourceScope,
    Organization,
    OrganizationMembership,
    OrganizationRole,
)
from muxivo_console.infrastructure.persistence.models import (
    AuditEventRecord,
    MembershipResourceScopeRecord,
    OrganizationMembershipRecord,
    OrganizationRecord,
    UserRecord,
)


class SqlAlchemyUserStatusReader:
    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def get_status(self, *, user_id: UUID) -> UserStatus | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(UserRecord.status).where(UserRecord.id == user_id)
            )
            raw_status = result.scalar_one_or_none()
        if raw_status is None:
            return None
        try:
            return UserStatus(cast(str, raw_status))
        except ValueError:
            return None


class SqlAlchemyOrganizationCreationWriter:
    """Atomically create a tenant, its initial owner and the mandatory audit event."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def create(
        self,
        *,
        organization: Organization,
        owner_membership: OrganizationMembership,
        audit_event: AuditEvent,
    ) -> bool:
        if owner_membership.id is None:
            raise ValueError(
                "Organization creation requires a server-generated membership identifier."
            )
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    session.add(
                        OrganizationRecord(
                            id=organization.id,
                            name=organization.name,
                            slug=organization.slug,
                        )
                    )
                    # The membership and audit records refer to the new tenant,
                    # but domain objects intentionally carry no ORM relation.
                    await session.flush()
                    session.add_all(
                        (
                            OrganizationMembershipRecord(
                                id=owner_membership.id,
                                organization_id=owner_membership.organization_id,
                                user_id=owner_membership.actor_id,
                                role=owner_membership.role.value,
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


class SqlAlchemyOrganizationMembershipReader:
    """Read Console-owned membership facts; malformed stored values fail closed."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def get_membership(
        self, *, actor_id: UUID, organization_id: UUID
    ) -> OrganizationMembership | None:
        async with self._session_factory() as session:
            membership_result = await session.execute(
                select(OrganizationMembershipRecord).where(
                    OrganizationMembershipRecord.user_id == actor_id,
                    OrganizationMembershipRecord.organization_id == organization_id,
                )
            )
            membership = membership_result.scalar_one_or_none()
            if membership is None:
                return None
            scope_result = await session.execute(
                select(MembershipResourceScopeRecord).where(
                    MembershipResourceScopeRecord.membership_id == membership.id
                )
            )
            scopes = scope_result.scalars().all()
        try:
            return OrganizationMembership(
                id=membership.id,
                actor_id=membership.user_id,
                organization_id=membership.organization_id,
                role=OrganizationRole(membership.role),
                resource_scopes=frozenset(
                    MembershipResourceScope(
                        resource=AuthorizationResource(scope.resource),
                        action=AuthorizationAction(scope.action),
                    )
                    for scope in scopes
                ),
            )
        except ValueError:
            return None
