"""Translate invitation ORM rows into secret-free domain projections."""

from muxivo_console.domain.authorization import AuthorizationAction, AuthorizationResource
from muxivo_console.domain.organization_invitations import (
    OrganizationInvitation,
    OrganizationInvitationDeliveryStatus,
)
from muxivo_console.domain.organizations import MembershipResourceScope, OrganizationRole
from muxivo_console.infrastructure.persistence.models import (
    OrganizationInvitationRecord,
    OrganizationInvitationScopeRecord,
)


def invitation_from_records(
    invitation: OrganizationInvitationRecord,
    scopes: tuple[OrganizationInvitationScopeRecord, ...],
) -> OrganizationInvitation | None:
    if invitation.invited_by_user_id is None:
        return None
    try:
        return OrganizationInvitation(
            id=invitation.id,
            organization_id=invitation.organization_id,
            invited_by_user_id=invitation.invited_by_user_id,
            email_lookup_hash=invitation.email_lookup_hash,
            email_hint=invitation.email_hint,
            email_ciphertext=invitation.email_ciphertext,
            token_hash=invitation.token_hash,
            role=OrganizationRole(invitation.role),
            resource_scopes=frozenset(
                MembershipResourceScope(
                    id=scope.id,
                    resource=AuthorizationResource(scope.resource),
                    action=AuthorizationAction(scope.action),
                )
                for scope in scopes
            ),
            expires_at=invitation.expires_at,
            created_at=invitation.created_at,
            accepted_at=invitation.accepted_at,
            revoked_at=invitation.revoked_at,
            delivery_status=(
                OrganizationInvitationDeliveryStatus(invitation.delivery_status)
                if invitation.delivery_status is not None
                else None
            ),
        )
    except (TypeError, ValueError):
        return None
