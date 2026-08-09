from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from muxivo_console.domain.activity import ControlModule, Platform
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.authorization import AuthorizationDecision, AuthorizationRequest
from muxivo_console.domain.connections import PlatformConnection
from muxivo_console.domain.identity import (
    EmailPasswordAccount,
    EmailPasswordRegistration,
    UserStatus,
)
from muxivo_console.domain.organizations import Organization, OrganizationMembership
from muxivo_console.domain.sessions import AuthSession


class ModuleCatalog(Protocol):
    """Outbound port implemented by a platform Control API adapter."""

    async def list_for_organization(
        self, *, organization_id: UUID, actor_id: UUID, correlation_id: UUID
    ) -> Sequence[ControlModule]: ...


class OrganizationAuthorizer(Protocol):
    """Inbound policy port, evaluated before every Console use case."""

    async def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision: ...


class OrganizationMembershipReader(Protocol):
    """Outbound port for the Console-owned organization membership store."""

    async def get_membership(
        self, *, actor_id: UUID, organization_id: UUID
    ) -> OrganizationMembership | None: ...


class IdentifierGenerator(Protocol):
    """Generates server-side UUIDv7 identifiers; clients never supply entity IDs."""

    def new(self) -> UUID: ...


class EmailAddressNormalizer(Protocol):
    """Validates and canonicalizes a browser-provided email address."""

    def normalize(self, value: str) -> str: ...


class EmailLookupHasher(Protocol):
    """Derives a keyed lookup value without persisting a plaintext e-mail."""

    def lookup_hash(self, normalized_email: str) -> str: ...


class EmailProtector(EmailLookupHasher, Protocol):
    """Encrypts an email; it also provides the keyed lookup derivation."""

    def encrypt(self, normalized_email: str) -> bytes: ...


class PasswordHasher(Protocol):
    """Hashes and verifies passwords without exposing a plaintext credential."""

    def hash(self, plaintext_password: str) -> str: ...

    def verify(self, encoded_hash: str, plaintext_password: str) -> bool: ...


class EmailPasswordRegistrationWriter(Protocol):
    """Atomically writes a registration and its audit event."""

    async def register(
        self, *, registration: EmailPasswordRegistration, audit_event: AuditEvent
    ) -> bool: ...


class UserStatusReader(Protocol):
    """Reads only the user lifecycle status needed to gate Console use cases."""

    async def get_status(self, *, user_id: UUID) -> UserStatus | None: ...


class OrganizationSlugGenerator(Protocol):
    """Creates a server-side, URL-safe organization slug."""

    def generate(self, organization_name: str) -> str: ...


class OrganizationCreationWriter(Protocol):
    """Atomically creates an organization, its owner membership and audit event."""

    async def create(
        self,
        *,
        organization: Organization,
        owner_membership: OrganizationMembership,
        audit_event: AuditEvent,
    ) -> bool: ...


class PlatformConnectionVerifier(Protocol):
    """Asks the platform service to validate native ownership before registration."""

    async def verify_registration(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        platform: Platform,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> bool: ...


class PlatformConnectionWriter(Protocol):
    """Atomically persists non-secret metadata and its mandatory audit event."""

    async def create(self, *, connection: PlatformConnection, audit_event: AuditEvent) -> bool: ...


class PlatformConnectionReader(Protocol):
    """Lists Console-owned non-secret connection metadata with keyset pagination."""

    async def list_for_organization(
        self, *, organization_id: UUID, after_id: UUID | None, limit: int
    ) -> Sequence[PlatformConnection]: ...


class Clock(Protocol):
    """Returns the current UTC instant; a port makes expiry behavior deterministic."""

    def now(self): ...


class OpaqueSessionTokenIssuer(Protocol):
    """Issues an opaque value that may be returned once to a browser cookie boundary."""

    def issue(self) -> str: ...


class SessionTokenHasher(Protocol):
    """Derives a keyed, fixed-size database lookup hash from a raw session token."""

    def hash(self, raw_token: str) -> str: ...


class AuthSessionWriter(Protocol):
    """Atomically persists a session and its mandatory security audit event."""

    async def create(self, *, session: AuthSession, audit_event: AuditEvent) -> bool: ...


class AuthSessionReader(Protocol):
    """Looks up a stored Console session by a keyed hash, never raw bearer data."""

    async def find_by_token_hash(self, *, token_hash: str) -> AuthSession | None: ...


class EmailPasswordAccountReader(Protocol):
    """Loads a password credential projection by a keyed email lookup hash."""

    async def find_by_email_lookup_hash(
        self, *, email_lookup_hash: str
    ) -> EmailPasswordAccount | None: ...
