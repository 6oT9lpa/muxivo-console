from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from muxivo_console.domain.activity import ControlModule
from muxivo_console.domain.audit import AuditEvent
from muxivo_console.domain.authorization import AuthorizationDecision, AuthorizationRequest
from muxivo_console.domain.identity import EmailPasswordRegistration
from muxivo_console.domain.organizations import OrganizationMembership


class ModuleCatalog(Protocol):
    """Outbound port implemented by a platform Control API adapter."""

    async def list_for_organization(
        self, *, organization_id: UUID, actor_id: UUID
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


class EmailProtector(Protocol):
    """Encrypts and derives a keyed lookup value for an email address."""

    def encrypt(self, normalized_email: str) -> bytes: ...

    def lookup_hash(self, normalized_email: str) -> str: ...


class PasswordHasher(Protocol):
    """Hashes and verifies passwords without exposing a plaintext credential."""

    def hash(self, plaintext_password: str) -> str: ...

    def verify(self, encoded_hash: str, plaintext_password: str) -> bool: ...


class EmailPasswordRegistrationWriter(Protocol):
    """Atomically writes a registration and its audit event."""

    async def register(
        self, *, registration: EmailPasswordRegistration, audit_event: AuditEvent
    ) -> bool: ...
