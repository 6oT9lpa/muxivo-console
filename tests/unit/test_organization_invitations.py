from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from muxivo_console.application.accept_organization_invitation import (
    AcceptOrganizationInvitation,
    AcceptOrganizationInvitationCommand,
    OrganizationInvitationAcceptanceRejectedError,
)
from muxivo_console.application.invite_organization_member import (
    InviteOrganizationMember,
    InviteOrganizationMemberCommand,
    OrganizationInvitationRejectedError,
)
from muxivo_console.application.revoke_organization_invitation import (
    OrganizationInvitationRevocationRejectedError,
    RevokeOrganizationInvitation,
    RevokeOrganizationInvitationCommand,
)
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.identity import UserStatus
from muxivo_console.domain.organization_invitations import (
    OrganizationInvitation,
    OrganizationInvitationDeliveryStatus,
    OrganizationInvitationStatus,
)
from muxivo_console.domain.organizations import (
    Organization,
    OrganizationMembership,
    OrganizationRole,
)

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


class FixedClock:
    def now(self):
        return NOW


class SequenceIdentifiers:
    def __init__(self, *identifiers: UUID) -> None:
        self._identifiers = iter(identifiers)

    def new(self) -> UUID:
        return next(self._identifiers)


class EmailProtector:
    def lookup_hash(self, normalized_email: str) -> str:
        return "e" * 64

    def encrypt(self, normalized_email: str) -> bytes:
        return b"encrypted-email"


class TokenIssuer:
    def issue(self) -> str:
        return "invite-token"


class TokenHasher:
    def hash(self, raw_token: str) -> str:
        return "t" * 64


class EmailNormalizer:
    def normalize(self, value: str) -> str:
        return value.strip().lower()


class OrganizationReader:
    async def find_by_id(self, *, organization_id: UUID) -> Organization | None:
        return Organization(organization_id, "Creator community", "creator-community")


class MembershipReader:
    def __init__(
        self, actor: OrganizationMembership, existing: OrganizationMembership | None = None
    ):
        self.actor = actor
        self.existing = existing

    async def get_membership(
        self, *, actor_id: UUID, organization_id: UUID
    ) -> OrganizationMembership | None:
        if self.existing is not None and actor_id == self.existing.actor_id:
            return self.existing
        if actor_id == self.actor.actor_id and organization_id == self.actor.organization_id:
            return self.actor
        return None


@dataclass
class InvitationWriter:
    invitation: OrganizationInvitation | None = None
    membership: OrganizationMembership | None = None
    accepted_at: datetime | None = None
    revoked_id: UUID | None = None
    delivery_status: OrganizationInvitationDeliveryStatus | None = None
    audit_event: AuditEvent | None = None

    async def create(self, *, invitation: OrganizationInvitation, audit_event: AuditEvent) -> bool:
        self.invitation = invitation
        self.audit_event = audit_event
        return True

    async def accept(
        self,
        *,
        invitation: OrganizationInvitation,
        membership: OrganizationMembership,
        accepted_at,
        audit_event: AuditEvent,
    ) -> bool:
        self.invitation = invitation
        self.membership = membership
        self.accepted_at = accepted_at
        self.audit_event = audit_event
        return True

    async def revoke(self, *, invitation_id, organization_id, revoked_at, audit_event) -> bool:
        self.revoked_id = invitation_id
        self.audit_event = audit_event
        return True

    async def update_delivery_status(
        self, *, invitation_id, organization_id, delivery_status
    ) -> bool:
        self.delivery_status = delivery_status
        return True


class InvitationNotifier:
    def __init__(self, delivered: bool = True) -> None:
        self.delivered = delivered
        self.payload = None

    async def send(self, **payload) -> bool:
        self.payload = payload
        return self.delivered


class UserEmails:
    def __init__(self, user_id: UUID | None) -> None:
        self.user_id = user_id

    async def find_active_user_id_by_email_lookup_hash(self, *, email_lookup_hash: str):
        return self.user_id


class UserStatuses:
    async def get_status(self, *, user_id: UUID):
        return UserStatus.ACTIVE


class InvitationReader:
    def __init__(self, invitation: OrganizationInvitation | None) -> None:
        self.invitation = invitation

    async def list_for_organization(self, *, organization_id: UUID):
        return (self.invitation,) if self.invitation is not None else ()

    async def find_for_organization(self, *, organization_id: UUID, invitation_id: UUID):
        if self.invitation is not None and self.invitation.id == invitation_id:
            return self.invitation
        return None

    async def find_pending_by_token_hash(self, *, token_hash: str, now):
        return self.invitation


def membership(
    actor_id: UUID, organization_id: UUID, role: OrganizationRole
) -> OrganizationMembership:
    return OrganizationMembership(
        id=uuid4(), actor_id=actor_id, organization_id=organization_id, role=role
    )


def invitation(organization_id: UUID, inviter_id: UUID) -> OrganizationInvitation:
    return OrganizationInvitation(
        id=uuid4(),
        organization_id=organization_id,
        invited_by_user_id=inviter_id,
        email_lookup_hash="e" * 64,
        email_hint="i***@example.com",
        email_ciphertext=b"encrypted-email",
        token_hash="t" * 64,
        role=OrganizationRole.VIEWER,
        resource_scopes=frozenset(),
        expires_at=NOW + timedelta(days=7),
        created_at=NOW,
    )


@pytest.mark.asyncio
async def test_invite_creates_masked_encrypted_invitation_and_delivers_link() -> None:
    actor_id, organization_id = uuid4(), uuid4()
    writer = InvitationWriter()
    notifier = InvitationNotifier()
    use_case = InviteOrganizationMember(
        identifiers=SequenceIdentifiers(uuid4(), uuid4()),
        clock=FixedClock(),
        email_normalizer=EmailNormalizer(),
        email_protector=EmailProtector(),
        token_issuer=TokenIssuer(),
        token_hasher=TokenHasher(),
        organizations=OrganizationReader(),
        memberships=MembershipReader(membership(actor_id, organization_id, OrganizationRole.OWNER)),
        invitations=writer,
        notifier=notifier,
    )

    result = await use_case.execute(
        InviteOrganizationMemberCommand(
            actor_id=actor_id,
            organization_id=organization_id,
            email="Invitee@Example.com",
            role=OrganizationRole.MODERATOR,
            resource_scopes=(),
            correlation_id=uuid4(),
        )
    )

    assert result.delivery_status == "sent"
    assert result.invitation.delivery_status is OrganizationInvitationDeliveryStatus.SENT
    assert writer.delivery_status is OrganizationInvitationDeliveryStatus.SENT
    assert result.invitation.email_hint == "i***@example.com"
    assert result.invitation.email_ciphertext == b"encrypted-email"
    assert result.invitation.token_hash == "t" * 64
    assert result.invitation.status_at(NOW) is OrganizationInvitationStatus.PENDING
    assert notifier.payload["raw_token"] == "invite-token"
    assert writer.audit_event is not None
    assert writer.audit_event.action == "organization.member.invitation.created"


@pytest.mark.asyncio
async def test_invite_rejects_equal_or_higher_role_without_persisting() -> None:
    actor_id, organization_id = uuid4(), uuid4()
    writer = InvitationWriter()
    use_case = InviteOrganizationMember(
        identifiers=SequenceIdentifiers(uuid4(), uuid4()),
        clock=FixedClock(),
        email_normalizer=EmailNormalizer(),
        email_protector=EmailProtector(),
        token_issuer=TokenIssuer(),
        token_hasher=TokenHasher(),
        organizations=OrganizationReader(),
        memberships=MembershipReader(membership(actor_id, organization_id, OrganizationRole.ADMIN)),
        invitations=writer,
        notifier=InvitationNotifier(),
    )

    with pytest.raises(OrganizationInvitationRejectedError):
        await use_case.execute(
            InviteOrganizationMemberCommand(
                actor_id=actor_id,
                organization_id=organization_id,
                email="person@example.com",
                role=OrganizationRole.ADMIN,
                resource_scopes=(),
                correlation_id=uuid4(),
            )
        )

    assert writer.invitation is None


@pytest.mark.asyncio
async def test_moderator_cannot_create_a_lower_role_invitation() -> None:
    actor_id, organization_id = uuid4(), uuid4()
    writer = InvitationWriter()
    use_case = InviteOrganizationMember(
        identifiers=SequenceIdentifiers(uuid4(), uuid4()),
        clock=FixedClock(),
        email_normalizer=EmailNormalizer(),
        email_protector=EmailProtector(),
        token_issuer=TokenIssuer(),
        token_hasher=TokenHasher(),
        organizations=OrganizationReader(),
        memberships=MembershipReader(
            membership(actor_id, organization_id, OrganizationRole.MODERATOR)
        ),
        invitations=writer,
        notifier=InvitationNotifier(),
    )

    with pytest.raises(OrganizationInvitationRejectedError):
        await use_case.execute(
            InviteOrganizationMemberCommand(
                actor_id=actor_id,
                organization_id=organization_id,
                email="person@example.com",
                role=OrganizationRole.VIEWER,
                resource_scopes=(),
                correlation_id=uuid4(),
            )
        )

    assert writer.invitation is None


@pytest.mark.asyncio
async def test_acceptance_requires_the_account_owning_invited_email() -> None:
    actor_id, other_user_id, organization_id = uuid4(), uuid4(), uuid4()
    stored_invitation = invitation(organization_id, uuid4())
    writer = InvitationWriter()
    use_case = AcceptOrganizationInvitation(
        clock=FixedClock(),
        identifiers=SequenceIdentifiers(uuid4(), uuid4()),
        token_hasher=TokenHasher(),
        user_emails=UserEmails(other_user_id),
        user_statuses=UserStatuses(),
        memberships=MembershipReader(membership(actor_id, organization_id, OrganizationRole.OWNER)),
        invitations=InvitationReader(stored_invitation),
        writer=writer,
    )

    with pytest.raises(OrganizationInvitationAcceptanceRejectedError):
        await use_case.execute(
            AcceptOrganizationInvitationCommand(
                actor_id=actor_id, raw_token="invite-token", correlation_id=uuid4()
            )
        )

    assert writer.membership is None


@pytest.mark.asyncio
async def test_acceptance_atomically_builds_membership_for_matching_account() -> None:
    actor_id, organization_id = uuid4(), uuid4()
    stored_invitation = invitation(organization_id, uuid4())
    writer = InvitationWriter()
    use_case = AcceptOrganizationInvitation(
        clock=FixedClock(),
        identifiers=SequenceIdentifiers(uuid4(), uuid4()),
        token_hasher=TokenHasher(),
        user_emails=UserEmails(actor_id),
        user_statuses=UserStatuses(),
        memberships=MembershipReader(membership(uuid4(), organization_id, OrganizationRole.OWNER)),
        invitations=InvitationReader(stored_invitation),
        writer=writer,
    )

    accepted_membership = await use_case.execute(
        AcceptOrganizationInvitationCommand(
            actor_id=actor_id, raw_token="invite-token", correlation_id=uuid4()
        )
    )

    assert accepted_membership.actor_id == actor_id
    assert accepted_membership.organization_id == organization_id
    assert accepted_membership.role is OrganizationRole.VIEWER
    assert writer.accepted_at == NOW
    assert writer.audit_event is not None
    assert writer.audit_event.action == "organization.member.invitation.accepted"


@pytest.mark.asyncio
async def test_revoke_only_allows_pending_invitation_below_actor_role() -> None:
    actor_id, organization_id = uuid4(), uuid4()
    stored_invitation = invitation(organization_id, uuid4())
    writer = InvitationWriter()
    use_case = RevokeOrganizationInvitation(
        clock=FixedClock(),
        identifiers=SequenceIdentifiers(uuid4()),
        memberships=MembershipReader(membership(actor_id, organization_id, OrganizationRole.ADMIN)),
        invitations=InvitationReader(stored_invitation),
        writer=writer,
    )

    await use_case.execute(
        RevokeOrganizationInvitationCommand(
            actor_id=actor_id,
            organization_id=organization_id,
            invitation_id=stored_invitation.id,
            correlation_id=uuid4(),
        )
    )

    assert writer.revoked_id == stored_invitation.id
    assert writer.audit_event is not None
    assert writer.audit_event.action == "organization.member.invitation.revoked"


@pytest.mark.asyncio
async def test_moderator_cannot_revoke_a_lower_role_invitation() -> None:
    actor_id, organization_id = uuid4(), uuid4()
    stored_invitation = invitation(organization_id, uuid4())
    writer = InvitationWriter()
    use_case = RevokeOrganizationInvitation(
        clock=FixedClock(),
        identifiers=SequenceIdentifiers(uuid4()),
        memberships=MembershipReader(
            membership(actor_id, organization_id, OrganizationRole.MODERATOR)
        ),
        invitations=InvitationReader(stored_invitation),
        writer=writer,
    )

    with pytest.raises(OrganizationInvitationRevocationRejectedError):
        await use_case.execute(
            RevokeOrganizationInvitationCommand(
                actor_id=actor_id,
                organization_id=organization_id,
                invitation_id=stored_invitation.id,
                correlation_id=uuid4(),
            )
        )

    assert writer.revoked_id is None
