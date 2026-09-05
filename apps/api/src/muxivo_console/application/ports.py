from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from muxivo_console.domain.activity import ControlModule, Platform
from muxivo_console.domain.ai_moderation import PlatformAiModerationSummary
from muxivo_console.domain.ai_moderation_policy import (
    PlatformAiModerationPolicy,
    PlatformAiModerationPolicyState,
)
from muxivo_console.domain.audit import AuditEvent, AuditLogEntry
from muxivo_console.domain.audit_timeline import PlatformAuditTimeline
from muxivo_console.domain.authorization import AuthorizationDecision, AuthorizationRequest
from muxivo_console.domain.bot_settings import PlatformBotSettings
from muxivo_console.domain.channel_purposes import ChannelPurpose, PlatformChannelPurposes
from muxivo_console.domain.channels import PlatformChannelCatalog
from muxivo_console.domain.connection_reconciliation import ConnectionReconciliationDecision
from muxivo_console.domain.connections import (
    PlatformConnection,
    PlatformConnectionLifecycleIdempotencyResult,
)
from muxivo_console.domain.dashboard import PlatformDashboardSummary
from muxivo_console.domain.health import PlatformHealth
from muxivo_console.domain.identity import (
    EmailPasswordAccount,
    EmailPasswordRegistration,
    LoginIdentity,
    LoginIdentityProfile,
    LoginIdentityProvider,
    PasswordCredential,
    UserStatus,
)
from muxivo_console.domain.identity_linking import IdentityLinkTransaction
from muxivo_console.domain.integrations import PlatformIntegrations
from muxivo_console.domain.oauth_login import OAuthLoginTransaction
from muxivo_console.domain.organization_invitations import (
    OrganizationInvitation,
    OrganizationInvitationDeliveryStatus,
)
from muxivo_console.domain.organizations import (
    Organization,
    OrganizationMemberProfile,
    OrganizationMembership,
    OrganizationMembershipProfile,
)
from muxivo_console.domain.password_recovery import PasswordRecoveryTransaction
from muxivo_console.domain.platform_connection_candidate_catalog import (
    PlatformConnectionCandidateCatalog,
)
from muxivo_console.domain.role_purposes import PlatformRolePurposes
from muxivo_console.domain.server_statistics import (
    PlatformServerStatistics,
)
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


class PlatformAuditTimelineReader(Protocol):
    """Reads an event-type/time-only timeline after native platform reauthorization."""

    async def get_audit_timeline_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformAuditTimeline: ...


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


class PlatformBotSettingsReader(Protocol):
    """Reads a non-secret settings projection after platform-native reauthorization."""

    async def get_bot_settings_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformBotSettings: ...


class PlatformIntegrationsReader(Protocol):
    async def get_integrations_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformIntegrations: ...


class PlatformServerStatisticsReader(Protocol):
    """Reads aggregate resource statistics after platform-native reauthorization."""

    async def get_server_statistics_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformServerStatistics: ...


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


class PlatformRolePurposesReader(Protocol):
    async def get_role_purposes_for_connection(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> PlatformRolePurposes: ...


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


class OrganizationListingReader(Protocol):
    """Reads organizations where the current actor already has a membership."""

    async def list_for_actor(
        self, *, actor_id: UUID
    ) -> Sequence[OrganizationMembershipProfile]: ...


class OrganizationReader(Protocol):
    """Loads one organization name for user-facing invitation delivery."""

    async def find_by_id(self, *, organization_id: UUID) -> Organization | None: ...


class OrganizationMemberReader(Protocol):
    """Reads members for one Console-owned organization."""

    async def list_profiles(self, organization_id: UUID) -> Sequence[OrganizationMemberProfile]: ...

    async def list_for_organization(
        self, organization_id: UUID
    ) -> Sequence[OrganizationMembership]: ...


class OrganizationMemberWriter(Protocol):
    """Writes organization membership changes with mandatory audit events."""

    async def add_member(
        self, *, membership: OrganizationMembership, audit_event: AuditEvent
    ) -> bool: ...

    async def update_member(
        self, *, membership: OrganizationMembership, audit_event: AuditEvent
    ) -> bool: ...

    async def remove_member(self, *, membership_id: UUID, audit_event: AuditEvent) -> bool: ...


class OrganizationInvitationReader(Protocol):
    """Reads invitation metadata without returning plaintext secrets."""

    async def list_for_organization(
        self, *, organization_id: UUID
    ) -> Sequence[OrganizationInvitation]: ...

    async def find_for_organization(
        self, *, organization_id: UUID, invitation_id: UUID
    ) -> OrganizationInvitation | None: ...

    async def find_pending_by_token_hash(
        self, *, token_hash: str, now
    ) -> OrganizationInvitation | None: ...


class OrganizationInvitationWriter(Protocol):
    """Atomically creates, accepts or revokes invitation state and audits it."""

    async def create(
        self, *, invitation: OrganizationInvitation, audit_event: AuditEvent
    ) -> bool: ...

    async def accept(
        self,
        *,
        invitation: OrganizationInvitation,
        membership: OrganizationMembership,
        accepted_at,
        audit_event: AuditEvent,
    ) -> bool: ...

    async def revoke(
        self, *, invitation_id: UUID, organization_id: UUID, revoked_at, audit_event: AuditEvent
    ) -> bool: ...

    async def update_delivery_status(
        self,
        *,
        invitation_id: UUID,
        organization_id: UUID,
        delivery_status: OrganizationInvitationDeliveryStatus,
    ) -> bool: ...


class IdentifierGenerator(Protocol):
    """Generates server-side UUIDv7 identifiers; clients never supply entity IDs."""

    def new(self) -> UUID: ...


class EmailAddressNormalizer(Protocol):
    """Validates and canonicalizes a browser-provided email address."""

    def normalize(self, value: str) -> str: ...


class EmailLookupHasher(Protocol):
    """Derives a keyed lookup value without persisting a plaintext e-mail."""

    def lookup_hash(self, normalized_email: str) -> str: ...


class UserEmailLookupReader(Protocol):
    """Resolves a normalized email lookup hash to an active first-party user."""

    async def find_active_user_id_by_email_lookup_hash(
        self, *, email_lookup_hash: str
    ) -> UUID | None: ...


class EmailProtector(EmailLookupHasher, Protocol):
    """Encrypts an email; it also provides the keyed lookup derivation."""

    def encrypt(self, normalized_email: str) -> bytes: ...

    def decrypt(self, ciphertext: bytes) -> str: ...


class PasswordHasher(Protocol):
    """Hashes and verifies passwords without exposing a plaintext credential."""

    def hash(self, plaintext_password: str) -> str: ...

    def verify(self, encoded_hash: str, plaintext_password: str) -> bool: ...


class PasswordCredentialReader(Protocol):
    """Reads one password credential for the authenticated user account."""

    async def find_for_user(self, *, user_id: UUID) -> PasswordCredential | None: ...


class PasswordCredentialWriter(Protocol):
    """Atomically updates one password credential and records a security audit fact."""

    async def change_password(
        self, *, user_id: UUID, password_hash: str, changed_at, audit_event: AuditEvent
    ) -> bool: ...


class BrowserSessionReauthenticationWriter(Protocol):
    """Atomically marks one active browser session recently authenticated."""

    async def reauthenticate(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        authenticated_at,
        audit_event: AuditEvent,
    ) -> bool: ...


class PasswordRecoveryTransactionWriter(Protocol):
    """Stores the durable recovery hash and audit fact.

    The short-lived Redis reference is managed by the application use cases;
    this port keeps the database transaction required for atomic credential
    rotation and session revocation.
    """

    async def create(
        self, *, transaction: PasswordRecoveryTransaction, audit_event: AuditEvent
    ) -> bool: ...


class PasswordRecoveryCompletionWriter(Protocol):
    """Consumes recovery token, rotates password, revokes sessions and audits atomically."""

    async def complete(
        self,
        *,
        token_hash: str,
        password_hash: str,
        completed_at,
        audit_id: UUID,
        correlation_id: UUID,
    ) -> UUID | None: ...


class PasswordRecoveryRecipientReader(Protocol):
    """Resolves the protected primary e-mail after a recovery succeeds."""

    async def find_primary_email(self, *, user_id: UUID) -> str | None: ...


class SecurityRecordCleaner(Protocol):
    """Deletes expired security records after their retention window has elapsed."""

    async def delete_expired_or_revoked_sessions(self, *, before) -> int: ...

    async def delete_consumed_or_expired_password_recovery_transactions(self, *, before) -> int: ...


class PasswordRecoveryNotifier(Protocol):
    """Delivers a raw recovery token through a configured out-of-band channel."""

    async def send(
        self,
        *,
        user_id: UUID,
        recipient_email: str,
        raw_token: str,
        expires_at,
        correlation_id: UUID,
    ) -> None: ...


class PasswordRecoveryCompletionNotifier(Protocol):
    """Confirms a completed password change without exposing recovery secrets."""

    async def send(
        self,
        *,
        user_id: UUID,
        recipient_email: str,
        changed_at,
        correlation_id: UUID,
    ) -> None: ...


class EmailPasswordRegistrationVerificationNotifier(Protocol):
    """Delivers a short-lived six-digit registration verification code."""

    async def send(
        self,
        *,
        registration_id: UUID,
        recipient_email: str,
        verification_code: str,
        expires_at,
        correlation_id: UUID,
    ) -> None: ...


class OneTimeTokenStore(Protocol):
    """Stores encrypted/hashed pending flow values with atomic exact-value consume."""

    async def put(self, *, key: str, value: str, ttl_seconds: int) -> bool: ...

    async def get(self, *, key: str) -> str | None: ...

    async def replace(self, *, key: str, value: str, ttl_seconds: int) -> bool: ...

    async def consume(self, *, key: str, value: str) -> bool: ...


class OrganizationInvitationNotifier(Protocol):
    """Delivers an invitation link without exposing its raw token to application logs."""

    async def send(
        self,
        *,
        invitation_id: UUID,
        organization_name: str,
        recipient_email: str,
        role: str,
        raw_token: str,
        expires_at,
        correlation_id: UUID,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0


class RateLimiter(Protocol):
    """Limits abuse-prone browser flows before they reach application use cases."""

    async def check(self, *, scope: str, key: str) -> RateLimitDecision: ...


class SessionFingerprintHasher(Protocol):
    """Creates keyed, browser-safe fingerprints for session security views."""

    def hash_ip_address(self, ip_address: str) -> str: ...

    def hash_user_agent(self, user_agent: str) -> str: ...


class HttpMetricsRecorder(Protocol):
    """Records process-local HTTP metrics for monitoring and alerting adapters."""

    def record_http_request(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_seconds: float,
    ) -> None: ...

    def render_prometheus(self) -> str: ...


class ReadinessProbe(Protocol):
    """Checks whether the composed Console can safely accept application traffic."""

    async def check(self, *, correlation_id: UUID) -> bool: ...


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


class LoginIdentityManagementReader(Protocol):
    """Reads browser-safe login identity projections for account management."""

    async def list_for_user(self, *, user_id: UUID) -> Sequence[LoginIdentityProfile]: ...


class LoginIdentityUnlinkWriter(Protocol):
    """Atomically removes one login identity and records a security audit fact."""

    async def unlink(
        self, *, identity_id: UUID, user_id: UUID, audit_event: AuditEvent
    ) -> bool: ...


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
    """Asks the platform service to validate native ownership before connecting."""

    async def verify_connection(
        self,
        *,
        actor_id: UUID,
        organization_id: UUID,
        platform: Platform,
        external_resource_id: str,
        correlation_id: UUID,
    ) -> bool: ...


class PlatformConnectionCandidateCatalogReader(Protocol):
    """Discovers selectable, browser-safe resources for one linked platform identity."""

    async def list_for_organization(
        self, *, organization_id: UUID, actor_id: UUID, correlation_id: UUID
    ) -> PlatformConnectionCandidateCatalog: ...


class PlatformConnectionCandidateReader(Protocol):
    """Routes candidate discovery to the adapter for the requested platform."""

    async def list_for_platform(
        self,
        *,
        organization_id: UUID,
        actor_id: UUID,
        platform: Platform,
        correlation_id: UUID,
    ) -> PlatformConnectionCandidateCatalog: ...


class PlatformConnectionWriter(Protocol):
    """Atomically persists non-secret metadata and its mandatory audit event."""

    async def create(self, *, connection: PlatformConnection, audit_event: AuditEvent) -> bool: ...


class PlatformConnectionLifecycleWriter(Protocol):
    """Atomically changes connection lifecycle state and records its audit event."""

    async def update_status(
        self,
        *,
        connection: PlatformConnection,
        audit_event: AuditEvent,
        idempotency_key: str | None = None,
        idempotency_action: str | None = None,
    ) -> bool: ...

    async def find_idempotent_lifecycle_result(
        self, *, organization_id: UUID, idempotency_key: str
    ) -> PlatformConnectionLifecycleIdempotencyResult | None: ...


class PlatformConnectionReader(Protocol):
    """Lists Console-owned non-secret connection metadata with keyset pagination."""

    async def list_for_organization(
        self, *, organization_id: UUID, after_id: UUID | None, limit: int
    ) -> Sequence[PlatformConnection]: ...

    async def find_for_organization(
        self, *, organization_id: UUID, connection_id: UUID
    ) -> PlatformConnection | None: ...


class PlatformConnectionReconciliationReader(Protocol):
    """Reads non-disconnected connection records for periodic reconciliation."""

    async def list_reconcilable(self, *, limit: int) -> Sequence[PlatformConnection]: ...


class PlatformConnectionReconciliationProbe(Protocol):
    """Asks a platform adapter which Console lifecycle status should be visible."""

    async def inspect_connection(
        self, *, connection: PlatformConnection, correlation_id: UUID
    ) -> ConnectionReconciliationDecision: ...


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


class AuthSessionLastSeenUpdater(Protocol):
    """Refreshes session activity without accepting raw browser credentials."""

    async def touch_last_seen(
        self, *, session_id: UUID, user_id: UUID, last_seen_at: datetime
    ) -> bool: ...


class AuthSessionRevoker(Protocol):
    """Atomically revokes the current server-side session and records the security fact."""

    async def revoke(
        self, *, session_id: UUID, user_id: UUID, revoked_at, audit_event: AuditEvent
    ) -> bool: ...


class AuthSessionListingReader(Protocol):
    """Reads active first-party browser sessions for the authenticated user."""

    async def list_active_for_user(self, *, user_id: UUID, active_at) -> Sequence[AuthSession]: ...


class AuthSessionBulkRevoker(Protocol):
    """Atomically revokes all active first-party browser sessions for one user."""

    async def revoke_all_for_user(
        self, *, user_id: UUID, revoked_at, audit_event: AuditEvent
    ) -> int: ...


class EmailPasswordAccountReader(Protocol):
    """Loads a password credential projection by a keyed email lookup hash."""

    async def find_by_email_lookup_hash(
        self, *, email_lookup_hash: str
    ) -> EmailPasswordAccount | None: ...
