import type { ConnectablePlatform } from "../../utils/connectionWizard";
import type { ConsoleTheme } from "../../utils/theme";

export type Theme = ConsoleTheme;
export type ConsoleSection =
  | "overview"
  | "connections"
  | "members"
  | "security"
  | "discord"
  | "audit";

export type Organization = { id: string; name: string; slug: string };

export type BrowserSession = {
  id: string;
  is_current: boolean;
  assurance_level: "password" | "recent_authentication";
  authenticated_at: string | null;
  last_seen_at: string | null;
  expires_at: string;
  device_label: string;
  ip_fingerprint: string | null;
  user_agent_fingerprint: string | null;
};

export type LoginIdentity = {
  id: string;
  provider: "email" | "discord" | "twitch" | "google" | "yandex";
  linked_at: string;
  last_used_at: string | null;
  can_unlink: boolean;
};

export type OrganizationRole = "owner" | "admin" | "moderator" | "analyst" | "viewer";

export type AuthorizationResource =
  | "console.control_modules"
  | "console.platform_connections"
  | "console.audit_events"
  | "console.organization_members";

export type AuthorizationAction = "read" | "manage";
export type MembershipScopeInput = {
  resource: AuthorizationResource;
  action: AuthorizationAction;
};

export type OrganizationMembership = {
  id: string | null;
  organization_id: string;
  user_id: string;
  display_name: string | null;
  role: OrganizationRole;
  resource_scopes: {
    id: string | null;
    resource: AuthorizationResource;
    action: AuthorizationAction;
  }[];
};

export type OrganizationListItem = {
  organization: Organization;
  membership: OrganizationMembership;
};

export type OrganizationInvitation = {
  id: string;
  organization_id: string;
  email_hint: string;
  role: OrganizationRole;
  resource_scopes: {
    id: string | null;
    resource: AuthorizationResource;
    action: AuthorizationAction;
  }[];
  status: "pending" | "accepted" | "revoked" | "expired";
  expires_at: string;
  created_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  delivery_status: "sent" | "unavailable" | "failed" | null;
};

export type PlatformConnectionGrantedScope = {
  key: string;
  display_name: string;
  description: string;
  status: "pending" | "granted" | "requires_reauthorization" | "revoked";
};

export type PlatformConnectionStatusReason =
  | "initial_pending"
  | "healthy"
  | "preflight_failed"
  | "token_expired"
  | "scopes_missing"
  | "platform_unreachable"
  | "resource_removed"
  | "reauthorized"
  | "revoked"
  | "disconnected";

export type PlatformConnection = {
  id: string;
  organization_id: string;
  platform: "discord" | "twitch" | "telegram";
  external_resource_id: string;
  status: "pending" | "active" | "degraded" | "reauth_required" | "disconnected";
  status_reason: PlatformConnectionStatusReason | null;
  granted_scopes: PlatformConnectionGrantedScope[];
};

export type PlatformConnectionCandidate = {
  platform: "discord" | "twitch";
  external_resource_id: string;
  display_name: string;
};

export type PlatformConnectionCandidateCatalog = {
  platform: "discord" | "twitch";
  identity_linked: boolean;
  items: PlatformConnectionCandidate[];
};

export type PlatformHealthSignal = {
  key: string;
  display_name: string;
  value: string;
  status: "operational" | "degraded";
  latency_ms: number | null;
};

export type PlatformHealth = {
  organization_id: string;
  platform: "discord" | "twitch" | "telegram";
  signals: PlatformHealthSignal[];
};

export type ControlModule = {
  key: string;
  display_name: string;
  platform: "discord" | "twitch" | "telegram";
  capability: "view" | "manage";
  status: "available" | "unavailable" | "requires_reauthorization";
};

export type PlatformDashboardSummary = {
  organization_id: string;
  connection_id: string;
  platform: "discord" | "twitch" | "telegram";
  messages_today: number;
  ai_flagged_today: number;
  creator_sources: number;
  bot_latency_ms: number | null;
};

export type PlatformChannel = {
  id: string;
  name: string;
  kind: "text" | "voice" | "announcement";
};

export type PlatformChannelCatalog = {
  organization_id: string;
  connection_id: string;
  platform: "discord" | "twitch" | "telegram";
  items: PlatformChannel[];
};

export type PlatformBotSettings = {
  organization_id: string;
  connection_id: string;
  platform: "discord" | "twitch" | "telegram";
  subscription_tier: string;
  activity_rotation_enabled: boolean;
  activity_rotation_interval_seconds: number;
  retention_days: Record<string, number>;
};

export type PlatformIntegrations = {
  discord_bot_status: string;
  creator_platforms_status: string;
  creator_poll_interval_seconds: number;
  creator_sources: { platform: string; total: number; active: number }[];
  muxivo_core_status: string;
  database_status: string;
};

export type PlatformServerStatistics = {
  organization_id: string;
  connection_id: string;
  platform: "discord" | "twitch" | "telegram";
  period_days: number;
  total_messages: number;
  active_users: number;
  active_channels: number;
  current_member_count: number;
  total_voice_minutes: number;
  joins: number;
  leaves: number;
  net_member_growth: number;
  moderation_events: number;
};

export type PlatformAuditTimeline = {
  organization_id: string;
  connection_id: string;
  platform: "discord" | "twitch" | "telegram";
  items: { event_type: string; occurred_at: string }[];
  limit: number;
};

export type PlatformWelcomeSettings = {
  organization_id: string;
  connection_id: string;
  platform: "discord";
  title: string;
  description: string;
  thumbnail_url: string | null;
  footer_text: string | null;
  footer_icon_url: string | null;
  color: number;
  is_enabled: boolean;
  rules_channel_id: string | null;
  roles_channel_id: string | null;
};

export type PlatformChannelPurposes = {
  items: { purpose: string; channel_id: string }[];
};

export type PlatformAiModerationSummary = {
  enforcement_mode: string;
  test_mode: boolean;
  is_default_policy: boolean;
  covered_channel_count: number;
  log_channel_configured: boolean;
  label_count: number;
  blacklist_word_count: number;
  allowed_domain_count: number;
  automated_timeout_enabled: boolean;
  automated_kick_enabled: boolean;
  automated_ban_enabled: boolean;
};

export type AiModerationAction =
  | "IGNORE"
  | "LOG"
  | "REVIEW"
  | "WARN"
  | "DELETE"
  | "DELETE_WARN"
  | "TIMEOUT"
  | "KICK"
  | "BAN";

export type AiModerationLabelRule = {
  risk_threshold: number;
  min_action: AiModerationAction;
  max_action: AiModerationAction;
};

export type AiModerationPolicy = {
  blacklist_words: string[];
  allowed_domains: string[];
  labels: Record<string, AiModerationLabelRule>;
  blacklist_action: AiModerationAction;
  unapproved_domain_action: AiModerationAction;
  context_window_days: number;
  repeat_offender_threshold: number;
  repeat_offender_action: AiModerationAction;
  escalation_enabled: boolean;
  escalation_score_threshold: number;
  escalation_half_life_days: number;
  excluded_user_ids: string[];
  excluded_role_ids: string[];
  excluded_channel_ids: string[];
  exclude_bots: boolean;
  ocr_enabled: boolean;
  ocr_failure_mode: "SKIP" | "REVIEW";
  ocr_max_gif_frames: number;
  ocr_process_empty_result: boolean;
  test_mode: boolean;
  enforcement_mode: "SHADOW" | "LIMITED" | "ELEVATED";
  limited_min_confidence: number;
  limited_hard_rule_labels: string[];
  beta_enforcement_acknowledged: boolean;
  allow_automated_timeout: boolean;
  allow_automated_kick: boolean;
  allow_automated_ban: boolean;
};

export type PlatformAiModerationPolicyState = {
  organization_id: string;
  connection_id: string;
  policy: AiModerationPolicy;
  is_default_policy: boolean;
};

export type AuditEvent = {
  id: string;
  correlation_id: string;
  actor_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  result: string;
  created_at: string;
};

export type AuditEventPage = {
  items: AuditEvent[];
  next_cursor: string | null;
};
