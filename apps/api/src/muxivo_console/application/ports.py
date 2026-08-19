from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from muxivo_console.domain.activity import ControlModule, Platform
from muxivo_console.domain.ai_moderation import PlatformAiModerationSummary
from muxivo_console.domain.ai_moderation_policy import (
    PlatformAiModerationPolicy,
    PlatformAiModerationPolicyState,
)
from muxivo_console.domain.audit import AuditEvent, AuditLogEntry
from muxivo_console.domain.authorization import AuthorizationDecision, AuthorizationRequest
from muxivo_console.domain.channel_purposes import ChannelPurpose, PlatformChannelPurposes
from muxivo_console.domain.channels import PlatformChannelCatalog
from muxivo_console.domain.connections import PlatformConnection
from muxivo_console.domain.dashboard import PlatformDashboardSummary
from muxivo_console.domain.health import PlatformHealth
from muxivo_console.domain.identity import (
    EmailPasswordAccount,
    EmailPasswordRegistration,
    LoginIdentity,
    LoginIdentityProvider,
    UserStatus,
)
from muxivo_console.domain.identity_linking import IdentityLinkTransaction
from muxivo_console.domain.oauth_login import OAuthLoginTransaction
from muxivo_console.domain.organizations import Organization, OrganizationMembership
from muxivo_console.domain.sessions import AuthSession
from muxivo_console.domain.welcome import PlatformWelcomeSettings


class ModuleCatalog(Protocol):
    """Outbound port implemented by a platform Control API adapter."""

    async def list_for_organization(
        self, *, organization_id: UUID, actor_id: UUID, correlation_id: UUID
    ) -> Sequence[ControlModule]: ...


class PlatformHealthReader(Protocol):
    """Reads aggregate, non-secret health from an authorized Control API."""

    async def get_for_organization(
        self, *, organization_id: UUID, actor_id: UUID, correlation_id: UUID
    ) -> PlatformHealth: ...


class PlatformDashboardReader(Protocol):
    """Reads a resource-bound, aggregate dashboard summary from a Control API."""

    async def get_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformDashboardSummary: ...


class PlatformChannelCatalogReader(Protocol):
    """Reads generic channels from one resource-bound platform connection."""

    async def get_channel_catalog_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformChannelCatalog: ...


class PlatformChannelPurposesReader(Protocol):
    async def get_channel_purposes_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformChannelPurposes: ...


class PlatformChannelPurposesWriter(Protocol):
    async def update_channel_purpose_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        purpose: ChannelPurpose,
        channel_id: str,
        correlation_id: UUID,
    ) -> PlatformChannelPurposes: ...


class PlatformAiModerationSummaryReader(Protocol):
    async def get_ai_moderation_summary_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformAiModerationSummary: ...


class PlatformAiModerationPolicyWriter(Protocol):
    """Writes a whole policy through a resource-bound platform Control API."""

    async def update_ai_moderation_policy_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        policy: PlatformAiModerationPolicy,
        correlation_id: UUID,
    ) -> PlatformAiModerationSummary: ...


class PlatformAiModerationPolicyReader(Protocol):
    """Reads a whole policy through a resource-bound platform Control API."""

    async def get_ai_moderation_policy_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformAiModerationPolicyState: ...


class PlatformWelcomeSettingsReader(Protocol):
    """Reads welcome configuration from one resource-bound platform connection."""

    async def get_welcome_settings_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformWelcomeSettings: ...


class PlatformWelcomeSettingsWriter(Protocol):
    """Updates welcome configuration through a resource-bound Control API command."""

    async def update_welcome_settings_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        settings: PlatformWelcomeSettings,
        correlation_id: UUID,
    ) -> PlatformWelcomeSettings: ...


class OrganizationAuthorizer(Protocol):
    """Inbound policy port, evaluated before every Console use case."""

    async def authorize(self, request: AuthorizationRequest) -> AuthorizationDecision: ...


class AuditEventWriter(Protocol):
    """Records one secret-free audit fact for an externally executed command."""

    async def record(self, event: AuditEvent) -> None: ...


class AuditEventReader(Protocol):
    """Reads keyset-paginated, organization-scoped, secret-free audit projections."""

    async def list_for_organization(
        self, *, organization_id: UUID, after_id: UUID | None, limit: int
    ) -> Sequence[AuditLogEntry]: ...


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


class LoginIdentityLinkWriter(Protocol):
    """Atomically stores a provider-verified external identity and its audit event."""

    async def link(self, *, identity: LoginIdentity, audit_event: AuditEvent) -> bool: ...


class LoginIdentityReader(Protocol):
    """Reads a Console-verified provider subject without exposing provider credentials."""

    async def find_provider_subject(
        self, *, user_id: UUID, provider: "LoginIdentityProvider"
    ) -> str | None: ...


class ProviderIdentityUserReader(Protocol):
    """Resolves a provider subject only when it is already linked to a Console user."""

    async def find_user_id(
        self, *, provider: "LoginIdentityProvider", provider_subject: str
    ) -> UUID | None: ...


class OpaqueValueProtector(Protocol):
    """Encrypts opaque browser-flow secrets before persistence."""

    def encrypt(self, plaintext: str) -> bytes: ...

    def decrypt(self, ciphertext: bytes) -> str: ...


class IdentityLinkTransactionWriter(Protocol):
    """Stores a single-use OAuth transaction before redirecting a browser."""

    async def create(
        self, *, transaction: IdentityLinkTransaction, audit_event: AuditEvent
    ) -> bool: ...


class IdentityLinkTransactionConsumer(Protocol):
    """Atomically claims an unexpired OAuth transaction so state cannot be replayed."""

    async def consume(self, *, state_hash: str, consumed_at) -> IdentityLinkTransaction | None: ...


class OAuthLoginTransactionWriter(Protocol):
    async def create(
        self, *, transaction: OAuthLoginTransaction, audit_event: AuditEvent
    ) -> bool: ...


class OAuthLoginTransactionConsumer(Protocol):
    async def consume(self, *, state_hash: str, consumed_at) -> OAuthLoginTransaction | None: ...


class OAuthIdentityProvider(Protocol):
    """Exchanges an authorization code server-side and returns a verified subject."""

    async def resolve_subject(self, *, authorization_code: str, code_verifier: str) -> str: ...


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

    async def find_for_organization(
        self, *, organization_id: UUID, connection_id: UUID
    ) -> PlatformConnection | None: ...


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


class AuthSessionRevoker(Protocol):
    """Atomically revokes the current server-side session and records the security fact."""

    async def revoke(
        self, *, session_id: UUID, user_id: UUID, revoked_at, audit_event: AuditEvent
    ) -> bool: ...


class EmailPasswordAccountReader(Protocol):
    """Loads a password credential projection by a keyed email lookup hash."""

    async def find_by_email_lookup_hash(
        self, *, email_lookup_hash: str
    ) -> EmailPasswordAccount | None: ...
