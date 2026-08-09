"""Use case for creating a Console organization and its initial owner membership."""

from dataclasses import dataclass
from uuid import UUID

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


class OrganizationCreationRejectedError(PermissionError):
    """Raised when the current user may not create an organization."""


@dataclass(frozen=True, slots=True)
class CreateOrganizationCommand:
    actor_id: UUID
    name: str
    correlation_id: UUID


@dataclass(slots=True)
class CreateOrganization:
    identifiers: IdentifierGenerator
    user_statuses: UserStatusReader
    slugs: OrganizationSlugGenerator
    organizations: OrganizationCreationWriter

    async def execute(self, command: CreateOrganizationCommand) -> Organization:
        if await self.user_statuses.get_status(user_id=command.actor_id) is not UserStatus.ACTIVE:
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
            raise OrganizationCreationRejectedError("The organization could not be created.")
        return organization
