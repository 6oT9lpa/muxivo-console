"""Use case for adding an active Console user to an organization."""

import logging
from dataclasses import dataclass

from muxivo_console.application.add_organization_member_command import AddOrganizationMemberCommand
from muxivo_console.application.organization_member_management_error import (
    OrganizationMemberManagementRejectedError,
)
from muxivo_console.application.organization_member_management_helpers import (
    assign_scope_ids,
    create_member_audit_event,
    reject_scopes_not_supported_by_role,
    require_actor_can_manage,
)
from muxivo_console.application.ports import (
    EmailAddressNormalizer,
    EmailLookupHasher,
    IdentifierGenerator,
    OrganizationMembershipReader,
    OrganizationMemberWriter,
    UserEmailLookupReader,
    UserStatusReader,
)
from muxivo_console.domain.identity import UserStatus
from muxivo_console.domain.organizations import OrganizationMembership

logger = logging.getLogger("muxivo_console.application.manage_organization_members")


@dataclass(slots=True)
class AddOrganizationMember:
    """Add an already registered user while enforcing role and scope boundaries."""

    identifiers: IdentifierGenerator
    email_normalizer: EmailAddressNormalizer
    email_lookup_hasher: EmailLookupHasher
    invitees: UserEmailLookupReader
    user_statuses: UserStatusReader
    memberships: OrganizationMembershipReader
    members: OrganizationMemberWriter

    async def execute(self, command: AddOrganizationMemberCommand) -> OrganizationMembership:
        normalized_email = self.email_normalizer.normalize(command.email)
        email_lookup_hash = self.email_lookup_hasher.lookup_hash(normalized_email)
        logger.info(
            "organization.member.add.started",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(command.organization_id),
                "target_email_lookup_hash_prefix": email_lookup_hash[:12],
                "role": command.role.value,
                "correlation_id": str(command.correlation_id),
            },
        )
        actor = await require_actor_can_manage(
            self.memberships, command.actor_id, command.organization_id, command.role
        )
        reject_scopes_not_supported_by_role(
            role=command.role,
            scopes=command.resource_scopes,
            actor_id=command.actor_id,
            organization_id=command.organization_id,
            correlation_id=command.correlation_id,
            operation="add",
        )
        target_user_id = await self.invitees.find_active_user_id_by_email_lookup_hash(
            email_lookup_hash=email_lookup_hash
        )
        if target_user_id is None:
            logger.warning(
                "organization.member.add.rejected_unknown_invitee",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "target_email_lookup_hash_prefix": email_lookup_hash[:12],
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationMemberManagementRejectedError("Invitee user is unavailable.")
        if await self.user_statuses.get_status(user_id=target_user_id) is not UserStatus.ACTIVE:
            logger.warning(
                "organization.member.add.rejected_inactive_target",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "target_user_id": str(target_user_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationMemberManagementRejectedError("Target user is not active.")
        membership = OrganizationMembership(
            id=self.identifiers.new(),
            actor_id=target_user_id,
            organization_id=command.organization_id,
            role=command.role,
            resource_scopes=assign_scope_ids(self.identifiers, command.resource_scopes),
        )
        created = await self.members.add_member(
            membership=membership,
            audit_event=create_member_audit_event(
                self.identifiers,
                command.correlation_id,
                command.actor_id,
                command.organization_id,
                "organization.member.add",
                target_user_id,
            ),
        )
        if not created:
            logger.warning(
                "organization.member.add.conflict",
                extra={
                    "actor_id": str(actor.actor_id),
                    "organization_id": str(command.organization_id),
                    "target_user_id": str(target_user_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationMemberManagementRejectedError("Member could not be added.")
        logger.info(
            "organization.member.add.completed",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(command.organization_id),
                "membership_id": str(membership.id),
                "target_user_id": str(target_user_id),
                "correlation_id": str(command.correlation_id),
            },
        )
        return membership
