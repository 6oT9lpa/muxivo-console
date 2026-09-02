"""Create one-time organization membership invitations."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import timedelta
from uuid import UUID

from muxivo_console.application.ports import (
    Clock,
    EmailAddressNormalizer,
    EmailProtector,
    IdentifierGenerator,
    OpaqueSessionTokenIssuer,
    OrganizationInvitationNotifier,
    OrganizationInvitationWriter,
    OrganizationMembershipReader,
    OrganizationReader,
    SessionTokenHasher,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.organization_invitations import (
    OrganizationInvitation,
    OrganizationInvitationDeliveryStatus,
)
from muxivo_console.domain.organizations import MembershipResourceScope, OrganizationRole

logger = logging.getLogger(__name__)


class OrganizationInvitationRejectedError(PermissionError):
    """Safe failure for unauthorized or conflicting invitation operations."""


@dataclass(frozen=True, slots=True)
class InviteOrganizationMemberCommand:
    actor_id: UUID
    organization_id: UUID
    email: str
    role: OrganizationRole
    resource_scopes: tuple[MembershipResourceScope, ...]
    correlation_id: UUID


@dataclass(frozen=True, slots=True)
class OrganizationInvitationCreationResult:
    invitation: OrganizationInvitation
    delivery_status: str


@dataclass(slots=True)
class InviteOrganizationMember:
    """Persist an invitation first, then deliver its raw link out of band."""

    identifiers: IdentifierGenerator
    clock: Clock
    email_normalizer: EmailAddressNormalizer
    email_protector: EmailProtector
    token_issuer: OpaqueSessionTokenIssuer
    token_hasher: SessionTokenHasher
    organizations: OrganizationReader
    memberships: OrganizationMembershipReader
    invitations: OrganizationInvitationWriter
    notifier: OrganizationInvitationNotifier
    lifetime: timedelta = timedelta(days=7)

    async def execute(
        self, command: InviteOrganizationMemberCommand
    ) -> OrganizationInvitationCreationResult:
        normalized_email = self.email_normalizer.normalize(command.email)
        email_lookup_hash = self.email_protector.lookup_hash(normalized_email)
        logger.info(
            "organization.invitation.create.started",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(command.organization_id),
                "target_email_lookup_hash_prefix": email_lookup_hash[:12],
                "role": command.role.value,
                "scope_count": len(command.resource_scopes),
                "correlation_id": str(command.correlation_id),
            },
        )
        organization = await self.organizations.find_by_id(organization_id=command.organization_id)
        actor = await self.memberships.get_membership(
            actor_id=command.actor_id, organization_id=command.organization_id
        )
        if organization is None or actor is None or not actor.role.may_assign(command.role):
            logger.warning(
                "organization.invitation.create.denied",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "role": command.role.value,
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationInvitationRejectedError("Invitation creation denied.")
        unsupported_scopes = [
            scope for scope in command.resource_scopes if not command.role.supports_scope(scope)
        ]
        if unsupported_scopes:
            logger.warning(
                "organization.invitation.create.scopes_denied",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "role": command.role.value,
                    "unsupported_scope_count": len(unsupported_scopes),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationInvitationRejectedError(
                "Role does not support requested invitation scopes."
            )

        raw_token = self.token_issuer.issue()
        now = self.clock.now()
        invitation = OrganizationInvitation(
            id=self.identifiers.new(),
            organization_id=command.organization_id,
            invited_by_user_id=command.actor_id,
            email_lookup_hash=email_lookup_hash,
            email_hint=_masked_email_hint(normalized_email),
            email_ciphertext=self.email_protector.encrypt(normalized_email),
            token_hash=self.token_hasher.hash(raw_token),
            role=command.role,
            resource_scopes=_assign_scope_ids(self.identifiers, command.resource_scopes),
            expires_at=now + self.lifetime,
            created_at=now,
        )
        created = await self.invitations.create(
            invitation=invitation,
            audit_event=AuditEvent(
                id=self.identifiers.new(),
                correlation_id=command.correlation_id,
                actor_id=command.actor_id,
                organization_id=command.organization_id,
                action="organization.member.invitation.created",
                resource_type="organization_invitation",
                resource_id=str(invitation.id),
                result="succeeded",
            ),
        )
        if not created:
            logger.warning(
                "organization.invitation.create.conflict",
                extra={
                    "actor_id": str(command.actor_id),
                    "organization_id": str(command.organization_id),
                    "invitation_id": str(invitation.id),
                    "correlation_id": str(command.correlation_id),
                },
            )
            raise OrganizationInvitationRejectedError("Invitation could not be created.")

        delivery_status = OrganizationInvitationDeliveryStatus.FAILED
        try:
            delivered = await self.notifier.send(
                invitation_id=invitation.id,
                organization_name=organization.name,
                recipient_email=normalized_email,
                role=invitation.role.value,
                raw_token=raw_token,
                expires_at=invitation.expires_at,
                correlation_id=command.correlation_id,
            )
            delivery_status = (
                OrganizationInvitationDeliveryStatus.SENT
                if delivered
                else OrganizationInvitationDeliveryStatus.UNAVAILABLE
            )
        except Exception as error:  # pragma: no cover - provider-specific failures are defensive
            logger.error(
                "organization.invitation.delivery.failed",
                extra={
                    "invitation_id": str(invitation.id),
                    "organization_id": str(invitation.organization_id),
                    "error_type": type(error).__name__,
                    "correlation_id": str(command.correlation_id),
                },
            )
        try:
            status_persisted = await self.invitations.update_delivery_status(
                invitation_id=invitation.id,
                organization_id=invitation.organization_id,
                delivery_status=delivery_status,
            )
        except Exception as error:  # pragma: no cover - database failures are defensive
            logger.error(
                "organization.invitation.delivery_status.persist_failed",
                extra={
                    "invitation_id": str(invitation.id),
                    "organization_id": str(invitation.organization_id),
                    "delivery_status": delivery_status.value,
                    "error_type": type(error).__name__,
                    "correlation_id": str(command.correlation_id),
                },
            )
        else:
            if not status_persisted:
                logger.error(
                    "organization.invitation.delivery_status.not_persisted",
                    extra={
                        "invitation_id": str(invitation.id),
                        "organization_id": str(invitation.organization_id),
                        "delivery_status": delivery_status.value,
                        "correlation_id": str(command.correlation_id),
                    },
                )
            else:
                logger.info(
                    "organization.invitation.delivery_status.persisted",
                    extra={
                        "invitation_id": str(invitation.id),
                        "organization_id": str(invitation.organization_id),
                        "delivery_status": delivery_status.value,
                        "correlation_id": str(command.correlation_id),
                    },
                )
        logger.info(
            "organization.invitation.create.completed",
            extra={
                "actor_id": str(command.actor_id),
                "organization_id": str(command.organization_id),
                "invitation_id": str(invitation.id),
                "delivery_status": delivery_status.value,
                "correlation_id": str(command.correlation_id),
            },
        )
        return OrganizationInvitationCreationResult(
            invitation=replace(invitation, delivery_status=delivery_status),
            delivery_status=delivery_status.value,
        )


def _assign_scope_ids(
    identifiers: IdentifierGenerator, scopes: tuple[MembershipResourceScope, ...]
) -> frozenset[MembershipResourceScope]:
    return frozenset(
        MembershipResourceScope(
            id=scope.id or identifiers.new(),
            resource=scope.resource,
            action=scope.action,
        )
        for scope in scopes
    )


def _masked_email_hint(normalized_email: str) -> str:
    local_part, separator, domain = normalized_email.partition("@")
    if not separator:
        raise ValueError("Normalized invitation email must contain a domain.")
    mask_length = max(1, min(3, len(local_part) - 1))
    return f"{local_part[0]}{'*' * mask_length}@{domain}"
