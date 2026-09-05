"""Small policy and audit helpers shared by member management use cases."""

import logging
from uuid import UUID

from muxivo_console.application.organization_member_management_error import (
    OrganizationMemberManagementRejectedError,
)
from muxivo_console.application.ports import (
    IdentifierGenerator,
    OrganizationMembershipReader,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.organizations import (
    MembershipResourceScope,
    OrganizationMembership,
    OrganizationRole,
)

logger = logging.getLogger("muxivo_console.application.manage_organization_members")


def can_manage_organization_members(role: OrganizationRole) -> bool:
    """Return whether a role may enter the organization-member management boundary."""
    return role in {OrganizationRole.OWNER, OrganizationRole.ADMIN}


async def require_actor_can_manage(
    memberships: OrganizationMembershipReader,
    actor_id: UUID,
    organization_id: UUID,
    target_role: OrganizationRole,
) -> OrganizationMembership:
    """Require the actor to assign the requested role or fail closed."""
    actor = await memberships.get_membership(actor_id=actor_id, organization_id=organization_id)
    if (
        actor is None
        or not can_manage_organization_members(actor.role)
        or not actor.role.may_assign(target_role)
    ):
        logger.warning(
            "organization.member.manage.denied",
            extra={
                "actor_id": str(actor_id),
                "organization_id": str(organization_id),
                "target_role": target_role.value,
            },
        )
        raise OrganizationMemberManagementRejectedError("Member management denied.")
    return actor


def assign_scope_ids(
    identifiers: IdentifierGenerator, scopes: tuple[MembershipResourceScope, ...]
) -> frozenset[MembershipResourceScope]:
    """Ensure every accepted resource scope has a stable persistence identifier."""
    return frozenset(
        MembershipResourceScope(
            id=scope.id or identifiers.new(),
            resource=scope.resource,
            action=scope.action,
        )
        for scope in scopes
    )


def reject_scopes_not_supported_by_role(
    *,
    role: OrganizationRole,
    scopes: tuple[MembershipResourceScope, ...],
    actor_id: UUID,
    organization_id: UUID,
    correlation_id: UUID,
    operation: str,
) -> None:
    """Reject a role/scope combination before any membership write occurs."""
    unsupported = [scope for scope in scopes if not role.supports_scope(scope)]
    if not unsupported:
        return
    logger.warning(
        "organization.member.scopes.rejected",
        extra={
            "actor_id": str(actor_id),
            "organization_id": str(organization_id),
            "role": role.value,
            "operation": operation,
            "unsupported_scope_count": len(unsupported),
            "correlation_id": str(correlation_id),
        },
    )
    raise OrganizationMemberManagementRejectedError("Role does not support requested scopes.")


def create_member_audit_event(
    identifiers: IdentifierGenerator,
    correlation_id: UUID,
    actor_id: UUID,
    organization_id: UUID,
    action: str,
    target_user_id: UUID,
) -> AuditEvent:
    """Create the audit fact paired atomically with a membership mutation."""
    return AuditEvent(
        id=identifiers.new(),
        correlation_id=correlation_id,
        actor_id=actor_id,
        organization_id=organization_id,
        action=action,
        resource_type="organization_member",
        resource_id=str(target_user_id),
        result="succeeded",
    )
