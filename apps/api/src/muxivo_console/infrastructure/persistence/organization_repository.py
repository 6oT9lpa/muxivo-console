"""SQLAlchemy adapters for Console-owned organizations, memberships and user status."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import cast
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.authorization import AuthorizationAction, AuthorizationResource
from muxivo_console.domain.identity import UserStatus
from muxivo_console.domain.organizations import (
    MembershipResourceScope,
    Organization,
    OrganizationMembership,
    OrganizationMembershipProfile,
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
            return _membership_from_record(membership, scopes)
        except ValueError:
            return None


class SqlAlchemyOrganizationListingReader:
    """Read organizations available to the current actor for the frontend switcher."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def list_for_actor(self, *, actor_id: UUID) -> tuple[OrganizationMembershipProfile, ...]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(OrganizationRecord, OrganizationMembershipRecord)
                .join(
                    OrganizationMembershipRecord,
                    OrganizationMembershipRecord.organization_id == OrganizationRecord.id,
                )
                .where(OrganizationMembershipRecord.user_id == actor_id)
                .order_by(OrganizationRecord.name, OrganizationRecord.id)
            )
            rows = result.all()
            membership_ids = [membership.id for _, membership in rows]
            scopes_by_membership_id = await _scopes_by_membership_id(session, membership_ids)
        profiles: list[OrganizationMembershipProfile] = []
        for organization_record, membership_record in rows:
            try:
                profiles.append(
                    OrganizationMembershipProfile(
                        organization=Organization(
                            id=organization_record.id,
                            name=organization_record.name,
                            slug=organization_record.slug,
                        ),
                        membership=_membership_from_record(
                            membership_record,
                            scopes_by_membership_id.get(membership_record.id, ()),
                        ),
                    )
                )
            except ValueError:
                continue
        return tuple(profiles)


class SqlAlchemyOrganizationMemberRepository:
    """Read and mutate organization members with an audit event in every transaction."""

    def __init__(
        self, session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]]
    ) -> None:
        self._session_factory = session_factory

    async def list_for_organization(
        self, organization_id: UUID
    ) -> tuple[OrganizationMembership, ...]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(OrganizationMembershipRecord)
                .where(OrganizationMembershipRecord.organization_id == organization_id)
                .order_by(OrganizationMembershipRecord.role, OrganizationMembershipRecord.user_id)
            )
            records = result.scalars().all()
            scopes_by_membership_id = await _scopes_by_membership_id(
                session, [record.id for record in records]
            )
        members: list[OrganizationMembership] = []
        for record in records:
            try:
                members.append(
                    _membership_from_record(record, scopes_by_membership_id.get(record.id, ()))
                )
            except ValueError:
                continue
        return tuple(members)

    async def add_member(
        self, *, membership: OrganizationMembership, audit_event: AuditEvent
    ) -> bool:
        if membership.id is None:
            raise ValueError("Adding an organization member requires a membership identifier.")
        try:
            async with self._session_factory() as session:
                async with session.begin():
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
                            _scope_record(membership.id, scope)
                            for scope in membership.resource_scopes
                        )
                        + (_audit_record(audit_event),)
                    )
                    await session.flush()
        except IntegrityError:
            return False
        return True

    async def update_member(
        self, *, membership: OrganizationMembership, audit_event: AuditEvent
    ) -> bool:
        if membership.id is None:
            raise ValueError("Updating an organization member requires a membership identifier.")
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    result = await session.execute(
                        update(OrganizationMembershipRecord)
                        .where(OrganizationMembershipRecord.id == membership.id)
                        .values(role=membership.role.value)
                    )
                    if result.rowcount != 1:
                        return False
                    await session.execute(
                        delete(MembershipResourceScopeRecord).where(
                            MembershipResourceScopeRecord.membership_id == membership.id
                        )
                    )
                    session.add_all(
                        tuple(
                            _scope_record(membership.id, scope)
                            for scope in membership.resource_scopes
                        )
                        + (_audit_record(audit_event),)
                    )
                    await session.flush()
        except IntegrityError:
            return False
        return True

    async def remove_member(self, *, membership_id: UUID, audit_event: AuditEvent) -> bool:
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    result = await session.execute(
                        delete(OrganizationMembershipRecord).where(
                            OrganizationMembershipRecord.id == membership_id
                        )
                    )
                    if result.rowcount != 1:
                        return False
                    session.add(_audit_record(audit_event))
                    await session.flush()
        except IntegrityError:
            return False
        return True


async def _scopes_by_membership_id(
    session: AsyncSession, membership_ids: list[UUID]
) -> dict[UUID, tuple[MembershipResourceScopeRecord, ...]]:
    if not membership_ids:
        return {}
    scope_result = await session.execute(
        select(MembershipResourceScopeRecord).where(
            MembershipResourceScopeRecord.membership_id.in_(membership_ids)
        )
    )
    grouped: dict[UUID, list[MembershipResourceScopeRecord]] = {}
    for scope in scope_result.scalars().all():
        grouped.setdefault(scope.membership_id, []).append(scope)
    return {membership_id: tuple(scopes) for membership_id, scopes in grouped.items()}


def _membership_from_record(
    membership: OrganizationMembershipRecord,
    scopes: tuple[MembershipResourceScopeRecord, ...],
) -> OrganizationMembership:
    return OrganizationMembership(
        id=membership.id,
        actor_id=membership.user_id,
        organization_id=membership.organization_id,
        role=OrganizationRole(membership.role),
        resource_scopes=frozenset(
            MembershipResourceScope(
                id=scope.id,
                resource=AuthorizationResource(scope.resource),
                action=AuthorizationAction(scope.action),
            )
            for scope in scopes
        ),
    )


def _scope_record(
    membership_id: UUID, scope: MembershipResourceScope
) -> MembershipResourceScopeRecord:
    if scope.id is None:
        raise ValueError("Membership resource scopes must have server-generated identifiers.")
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
