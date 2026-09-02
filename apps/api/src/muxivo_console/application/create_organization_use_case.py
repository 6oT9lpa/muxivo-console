"""Create a Console organization and its initial owner membership."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from muxivo_console.application.create_organization_command import CreateOrganizationCommand
from muxivo_console.application.organization_creation_rejected_error import (
    OrganizationCreationRejectedError,
)
from muxivo_console.application.ports import (
    IdentifierGenerator,
    OrganizationCreationWriter,
    OrganizationSlugGenerator,
    UserStatusReader,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import UserStatus
from muxivo_console.domain.organizations import (
    Organization,
    OrganizationMembership,
    OrganizationRole,
)

logger = logging.getLogger("muxivo_console.application.create_organization")


@dataclass(slots=True)
class CreateOrganization:
    """Create an organization and atomically grant its actor the owner role."""

    identifiers: IdentifierGenerator
    user_statuses: UserStatusReader
    slugs: OrganizationSlugGenerator
    organizations: OrganizationCreationWriter

    async def execute(self, command: CreateOrganizationCommand) -> Organization:
        logger.info(
            "organization.create.started",
            extra={
                "actor_id": str(command.actor_id),
                "correlation_id": str(command.correlation_id),
            },
        )
        if await self.user_statuses.get_status(user_id=command.actor_id) is not UserStatus.ACTIVE:
            logger.warning(
                "organization.create.rejected_inactive_user",
                extra={
                    "actor_id": str(command.actor_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationCreationRejectedError(
                "The user is not allowed to create an organization."
            )

        organization = Organization(
            id=self.identifiers.new(),
            name=command.name,
            slug=self.slugs.generate(command.name),
        )
        owner_membership = OrganizationMembership(
            actor_id=command.actor_id,
            organization_id=organization.id,
            role=OrganizationRole.OWNER,
            id=self.identifiers.new(),
        )
        created = await self.organizations.create(
            organization=organization,
            owner_membership=owner_membership,
            audit_event=AuditEvent(
                id=self.identifiers.new(),
                correlation_id=command.correlation_id,
                actor_id=command.actor_id,
                organization_id=organization.id,
                action="organization.create",
                resource_type="organization",
                resource_id=str(organization.id),
                result="succeeded",
            ),
        )
        if not created:
            logger.warning(
                "organization.create.rejected_conflict",
                extra={
                    "actor_id": str(command.actor_id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationCreationRejectedError("The organization could not be created.")
        logger.info(
            "organization.create.completed",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(organization.id),
                "correlation_id": str(command.correlation_id),
            },
        )
        return organization
