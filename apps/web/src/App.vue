<script setup lang="ts">
import {
  Activity,
  Cable,
  ClipboardList,
  LayoutDashboard,
  LogOut,
  Moon,
  ShieldCheck,
  Sun,
  UsersRound,
} from "@lucide/vue";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { consoleApi, ConsoleApiError } from "./api/consoleApi";
import LanguageSwitcher from "./components/common/LanguageSwitcher.vue";
import PublicFooter from "./components/common/PublicFooter.vue";
import { useI18n } from "./i18n";
import { clientLogger } from "./utils/clientLogger";
import {
  passwordChangeValidationMessage,
  passwordRecoveryCompletionValidationMessage,
} from "./utils/passwordChange";
import { accountRegistrationValidationMessage } from "./utils/accountRegistration";
import {
  ACTIVE_ORGANIZATION_STORAGE_KEY,
  chooseActiveOrganizationId,
  persistActiveOrganizationId,
} from "./utils/organizations";
import { supportedMemberScopesForRole } from "./utils/memberScopes";
import {
  nextConsoleTheme,
  persistConsoleTheme,
  readConsoleTheme,
  type ConsoleTheme,
} from "./utils/theme";
import {
  formatSecurityTimestamp,
} from "./utils/securityPresentation";
import {
  connectionWizardOptions,
  type ConnectablePlatform,
} from "./utils/connectionWizard";
import GetToKnowUs from "./views/GetToKnowUs.vue";
import MuxivoLanding from "./views/MuxivoLanding.vue";

const { t } = useI18n();
type Theme = ConsoleTheme;
type ConsoleSection = "overview" | "connections" | "members" | "security" | "discord" | "audit";

const initialTheme: Theme = readConsoleTheme(
  typeof window !== "undefined" ? window.localStorage : null,
);
const authMode = ref<"sign-in" | "create-account">("sign-in");
const email = ref("");
const password = ref("");
const registrationDisplayName = ref("");
const registrationEmail = ref("");
const registrationPassword = ref("");
const currentPassword = ref("");
const reauthenticationPassword = ref("");
const newPassword = ref("");
const confirmNewPassword = ref("");
const recoveryEmail = ref("");
const recoveryToken = ref("");
const recoveryNewPassword = ref("");
const recoveryConfirmPassword = ref("");
const invitationToken = ref(
  typeof window !== "undefined"
    ? new URL(window.location.href).searchParams.get("token") ?? ""
    : "",
);
const organizationName = ref("");
const authenticated = ref(false);
const landingTab = ref<"overview" | "about">("overview");
const loginOpen = ref(false);
const theme = ref<Theme>(initialTheme);
const activeConsoleSection = ref<ConsoleSection>("overview");
const busy = ref(false);
const notice = ref("");
const browserSessions = ref<BrowserSession[]>([]);
const loginIdentities = ref<LoginIdentity[]>([]);
const organizations = ref<OrganizationListItem[]>([]);
const organizationInvitations = ref<OrganizationInvitation[]>([]);
const selectedOrganizationId = ref(
  typeof window !== "undefined"
    ? window.localStorage.getItem(ACTIVE_ORGANIZATION_STORAGE_KEY) ?? ""
    : "",
);
const organizationMembers = ref<OrganizationMembership[]>([]);
const newMemberEmail = ref("");
const newMemberRole = ref<OrganizationRole>("viewer");
const newMemberScopes = ref<MembershipScopeInput[]>([
  { resource: "console.control_modules", action: "read" },
]);
const platform = ref<ConnectablePlatform>("discord");
const externalResourceId = ref("");
const connections = ref<PlatformConnection[]>([]);
const platformHealth = ref<PlatformHealth | null>(null);
const controlModules = ref<ControlModule[]>([]);
const selectedConnectionId = ref("");
const selectedDiscordConnectionId = ref("");
const dashboardSummary = ref<PlatformDashboardSummary | null>(null);
const channelCatalog = ref<PlatformChannelCatalog | null>(null);
const botSettings = ref<PlatformBotSettings | null>(null);
const integrations = ref<PlatformIntegrations | null>(null);
const serverStatistics = ref<PlatformServerStatistics | null>(null);
const auditTimeline = ref<PlatformAuditTimeline | null>(null);
const welcomeSettings = ref<PlatformWelcomeSettings | null>(null);
const channelPurposes = ref<PlatformChannelPurposes | null>(null);
const aiModerationSummary = ref<PlatformAiModerationSummary | null>(null);
const aiModerationPolicy = ref<PlatformAiModerationPolicyState | null>(null);
const aiModerationBlacklistWords = ref("");
const aiModerationAllowedDomains = ref("");
const auditEvents = ref<AuditEvent[]>([]);
const auditEventsNextCursor = ref<string | null>(null);
const selectedPurpose = ref("welcome");
const selectedPurposeChannelId = ref("");
const publicNavItems = computed(() => [
  { key: "overview" as const, label: t("header.we_are_muxivo") },
  { key: "about" as const, label: t("header.get_to_know_us") },
]);
const consoleNavItems = computed(() => [
  {
    key: "overview" as const,
    label: t("console.nav.overview"),
    description: t("console.nav.overview_description"),
    icon: LayoutDashboard,
  },
  {
    key: "connections" as const,
    label: t("console.nav.connections"),
    description: t("console.nav.connections_description"),
    icon: Cable,
  },
  {
    key: "members" as const,
    label: t("console.nav.members"),
    description: t("console.nav.members_description"),
    icon: UsersRound,
  },
  {
    key: "security" as const,
    label: t("console.nav.security"),
    description: t("console.nav.security_description"),
    icon: ShieldCheck,
  },
  {
    key: "discord" as const,
    label: t("console.nav.discord"),
    description: t("console.nav.discord_description"),
    icon: Activity,
  },
  {
    key: "audit" as const,
    label: t("console.nav.audit"),
    description: t("console.nav.audit_description"),
    icon: ClipboardList,
  },
]);
const activeConsoleNavItem = computed(
  () =>
    consoleNavItems.value.find((item) => item.key === activeConsoleSection.value) ??
    consoleNavItems.value[0],
);

const localizedConnectionWizardOptions = computed(() =>
  connectionWizardOptions.map((option) => ({
    ...option,
    title: t(`console.connections.wizard.${option.platform}.title`),
    summary: t(`console.connections.wizard.${option.platform}.summary`),
    actionLabel: t(`console.connections.wizard.${option.platform}.action`),
    resourceLabel: t(`console.connections.wizard.${option.platform}.resource`),
    resourceHelp: t(`console.connections.wizard.${option.platform}.help`),
    preflightSteps: option.preflightSteps.map((_, index) =>
      t(`console.connections.wizard.${option.platform}.step_${index + 1}`),
    ),
  })),
);

function toggleTheme(): void {
  theme.value = nextConsoleTheme(theme.value);
  persistConsoleTheme(typeof window !== "undefined" ? window.localStorage : null, theme.value);
  if (typeof document !== "undefined") {
    document.documentElement.style.colorScheme = theme.value;
  }
  clientLogger.info("console.theme.changed", { theme: theme.value });
}

function scrollToConsoleSection(section: ConsoleSection): void {
  activeConsoleSection.value = section;
  if (typeof document !== "undefined") {
    window.requestAnimationFrame(() => {
      document.getElementById(`console-${section}`)?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  }
  clientLogger.info("console.navigation.changed", { section });
}

const previousBodyOverflow = ref("");

watch(loginOpen, (isOpen) => {
  if (typeof document === "undefined") return;
  if (isOpen) {
    previousBodyOverflow.value = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return;
  }
  document.body.style.overflow = previousBodyOverflow.value;
});

onBeforeUnmount(() => {
  if (typeof document !== "undefined") document.body.style.overflow = previousBodyOverflow.value;
});

function navLetters(label: string): string[] {
  return Array.from(label);
}

type Organization = { id: string; name: string; slug: string };
type BrowserSession = {
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
type LoginIdentity = {
  id: string;
  provider: "email" | "discord" | "twitch" | "google" | "yandex";
  linked_at: string;
  last_used_at: string | null;
  can_unlink: boolean;
};
type OrganizationRole = "owner" | "admin" | "moderator" | "analyst" | "viewer";
type AuthorizationResource =
  | "console.control_modules"
  | "console.platform_connections"
  | "console.audit_events"
  | "console.organization_members";
type AuthorizationAction = "read" | "manage";
type MembershipScopeInput = { resource: AuthorizationResource; action: AuthorizationAction };
type OrganizationMembership = {
  id: string | null;
  organization_id: string;
  user_id: string;
  display_name: string | null;
  role: OrganizationRole;
  resource_scopes: { id: string | null; resource: AuthorizationResource; action: AuthorizationAction }[];
};
type OrganizationListItem = {
  organization: Organization;
  membership: OrganizationMembership;
};
type OrganizationInvitation = {
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
type PlatformConnectionGrantedScope = {
  key: string;
  display_name: string;
  description: string;
  status: "pending" | "granted" | "requires_reauthorization" | "revoked";
};
type PlatformConnection = {
  id: string;
  organization_id: string;
  platform: "discord" | "twitch" | "telegram";
  external_resource_id: string;
  status: "pending" | "active" | "degraded" | "reauth_required" | "disconnected";
  granted_scopes: PlatformConnectionGrantedScope[];
};
type PlatformHealthSignal = {
  key: string;
  display_name: string;
  value: string;
  status: "operational" | "degraded";
  latency_ms: number | null;
};
type PlatformHealth = {
  organization_id: string;
  platform: "discord" | "twitch" | "telegram";
  signals: PlatformHealthSignal[];
};
type ControlModule = {
  key: string;
  display_name: string;
  platform: "discord" | "twitch" | "telegram";
  capability: "view" | "manage";
  status: "available" | "unavailable" | "requires_reauthorization";
};
type PlatformDashboardSummary = {
  organization_id: string;
  connection_id: string;
  platform: "discord" | "twitch" | "telegram";
  messages_today: number;
  ai_flagged_today: number;
  creator_sources: number;
  bot_latency_ms: number | null;
};
type PlatformChannel = {
  id: string;
  name: string;
  kind: "text" | "voice" | "announcement";
};
type PlatformChannelCatalog = {
  organization_id: string;
  connection_id: string;
  platform: "discord" | "twitch" | "telegram";
  items: PlatformChannel[];
};
type PlatformBotSettings = {
  organization_id: string;
  connection_id: string;
  platform: "discord" | "twitch" | "telegram";
  subscription_tier: string;
  activity_rotation_enabled: boolean;
  activity_rotation_interval_seconds: number;
  retention_days: Record<string, number>;
};
type PlatformIntegrations = {
  discord_bot_status: string;
  creator_platforms_status: string;
  creator_poll_interval_seconds: number;
  creator_sources: { platform: string; total: number; active: number }[];
  muxivo_core_status: string;
  database_status: string;
};
type PlatformServerStatistics = {
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
type PlatformAuditTimeline = {
  organization_id: string;
  connection_id: string;
  platform: "discord" | "twitch" | "telegram";
  items: { event_type: string; occurred_at: string }[];
  limit: number;
};
type PlatformWelcomeSettings = {
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
type PlatformChannelPurposes = { items: { purpose: string; channel_id: string }[] };
type PlatformAiModerationSummary = {
  enforcement_mode: string; test_mode: boolean; is_default_policy: boolean;
  covered_channel_count: number; log_channel_configured: boolean; label_count: number;
  blacklist_word_count: number; allowed_domain_count: number;
  automated_timeout_enabled: boolean; automated_kick_enabled: boolean; automated_ban_enabled: boolean;
};
type AiModerationAction = "IGNORE" | "LOG" | "REVIEW" | "WARN" | "DELETE" | "DELETE_WARN" | "TIMEOUT" | "KICK" | "BAN";
type AiModerationLabelRule = { risk_threshold: number; min_action: AiModerationAction; max_action: AiModerationAction };
type AiModerationPolicy = {
  blacklist_words: string[]; allowed_domains: string[]; labels: Record<string, AiModerationLabelRule>;
  blacklist_action: AiModerationAction; unapproved_domain_action: AiModerationAction;
  context_window_days: number; repeat_offender_threshold: number; repeat_offender_action: AiModerationAction;
  escalation_enabled: boolean; escalation_score_threshold: number; escalation_half_life_days: number;
  excluded_user_ids: string[]; excluded_role_ids: string[]; excluded_channel_ids: string[]; exclude_bots: boolean;
  ocr_enabled: boolean; ocr_failure_mode: "SKIP" | "REVIEW"; ocr_max_gif_frames: number; ocr_process_empty_result: boolean;
  test_mode: boolean; enforcement_mode: "SHADOW" | "LIMITED" | "ELEVATED"; limited_min_confidence: number;
  limited_hard_rule_labels: string[]; beta_enforcement_acknowledged: boolean;
  allow_automated_timeout: boolean; allow_automated_kick: boolean; allow_automated_ban: boolean;
};
type PlatformAiModerationPolicyState = {
  organization_id: string; connection_id: string; policy: AiModerationPolicy; is_default_policy: boolean;
};
type AuditEvent = {
  id: string; correlation_id: string; actor_id: string | null; action: string;
  resource_type: string; resource_id: string | null; result: string; created_at: string;
};
type AuditEventPage = { items: AuditEvent[]; next_cursor: string | null };

const usableConnections = computed(() =>
  connections.value.filter(
    (connection) =>
      (connection.status === "active" || connection.status === "degraded"),
  ),
);
const usableDiscordConnections = computed(() =>
  usableConnections.value.filter((connection) => connection.platform === "discord"),
);
const selectedConnectionWizard = computed(
  () =>
    localizedConnectionWizardOptions.value.find((option) => option.platform === platform.value) ??
    localizedConnectionWizardOptions.value[0],
);
const selectedConnection = computed(() =>
  usableConnections.value.find((connection) => connection.id === selectedConnectionId.value) ?? null,
);
const selectedDiscordConnection = computed(
  () =>
    usableDiscordConnections.value.find(
      (connection) => connection.id === selectedDiscordConnectionId.value,
    ) ?? null,
);
const canRunSelectedDiscordWrites = computed(
  () => selectedDiscordConnection.value?.status === "active",
);
const activeOrganization = computed(
  () =>
    organizations.value.find(
      (item) => item.organization.id === selectedOrganizationId.value,
    ) ?? null,
);
const activeOrganizationId = computed(() => activeOrganization.value?.organization.id ?? "");
const canManageOrganizationMembers = computed(
  () =>
    activeOrganization.value?.membership.role === "owner" ||
    activeOrganization.value?.membership.role === "admin",
);
const currentBrowserSession = computed(
  () => browserSessions.value.find((session) => session.is_current) ?? null,
);
const canRevokeAllBrowserSessions = computed(
  () => currentBrowserSession.value?.assurance_level === "recent_authentication",
);
const memberRoleOptions: OrganizationRole[] = ["admin", "moderator", "analyst", "viewer"];
const availableMemberRoleOptions = computed<OrganizationRole[]>(() =>
  activeOrganization.value?.membership.role === "owner"
    ? memberRoleOptions
    : ["moderator", "analyst", "viewer"],
);
const memberScopeOptions: MembershipScopeInput[] = [
  { resource: "console.control_modules", action: "read" },
  { resource: "console.platform_connections", action: "read" },
  { resource: "console.platform_connections", action: "manage" },
  { resource: "console.audit_events", action: "read" },
  { resource: "console.organization_members", action: "manage" },
];
const availableNewMemberScopeOptions = computed(() =>
  supportedMemberScopesForRole(newMemberRole.value, memberScopeOptions),
);

async function signIn() {
  busy.value = true;
  notice.value = "";
  try {
    await consoleApi<void>("/api/v1/auth/email-password/sessions", {
      method: "POST",
      body: JSON.stringify({ email: email.value, password: password.value }),
    });
    authenticated.value = true;
    loginOpen.value = false;
    password.value = "";
    notice.value = t("console.notice.signed_in");
    await Promise.all([loadOrganizations(), loadBrowserSessions(), loadLoginIdentities()]);
    await acceptInvitationIfPresent();
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function createAccount() {
  const validationMessage = accountRegistrationValidationMessage({
    displayName: registrationDisplayName.value,
    email: registrationEmail.value,
    password: registrationPassword.value,
  });
  if (validationMessage) {
    notice.value = validationMessage;
    return;
  }
  busy.value = true;
  notice.value = "";
  try {
    await consoleApi<{ status: "accepted" }>("/api/v1/auth/email-password/registrations", {
      method: "POST",
      body: JSON.stringify({
        email: registrationEmail.value,
        password: registrationPassword.value,
        display_name: registrationDisplayName.value,
      }),
    });
    email.value = registrationEmail.value;
    password.value = "";
    registrationPassword.value = "";
    authMode.value = "sign-in";
    notice.value = t("console.notice.account_accepted");
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function signInWithDiscord() {
  busy.value = true;
  notice.value = "";
  try {
    const authorization = await consoleApi<{ authorization_url: string }>(
      "/api/v1/auth/discord/authorizations",
      { method: "POST" },
    );
    window.location.assign(authorization.authorization_url);
  } catch (error) {
    notice.value = messageFor(error);
    busy.value = false;
  }
}

async function requestPasswordRecovery() {
  busy.value = true;
  notice.value = "";
  try {
    await consoleApi<{ status: "accepted" }>("/api/v1/auth/password-recovery/requests", {
      method: "POST",
      body: JSON.stringify({ email: recoveryEmail.value || email.value }),
    });
    notice.value = t("console.notice.recovery_requested");
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function completePasswordRecovery() {
  const validationMessage = passwordRecoveryCompletionValidationMessage({
    token: recoveryToken.value,
    newPassword: recoveryNewPassword.value,
    confirmNewPassword: recoveryConfirmPassword.value,
  });
  if (validationMessage) {
    notice.value = validationMessage;
    return;
  }
  busy.value = true;
  notice.value = "";
  try {
    await consoleApi<void>("/api/v1/auth/password-recovery/completions", {
      method: "POST",
      body: JSON.stringify({
        token: recoveryToken.value,
        new_password: recoveryNewPassword.value,
      }),
    });
    recoveryToken.value = "";
    recoveryNewPassword.value = "";
    recoveryConfirmPassword.value = "";
    password.value = "";
    notice.value = t("console.notice.password_reset");
  } catch (error) {
    if (error instanceof ConsoleApiError && error.status === 403) {
      notice.value = t("console.notice.recovery_invalid");
    } else {
      notice.value = messageFor(error);
    }
  } finally {
    busy.value = false;
  }
}

async function signOut() {
  busy.value = true;
  notice.value = "";
  try {
    await consoleApi<void>("/api/v1/auth/session", { method: "DELETE" });
    authenticated.value = false;
    browserSessions.value = [];
    loginIdentities.value = [];
    currentPassword.value = "";
    reauthenticationPassword.value = "";
    newPassword.value = "";
    confirmNewPassword.value = "";
    connections.value = [];
    organizations.value = [];
    organizationInvitations.value = [];
    selectedOrganizationId.value = "";
    organizationMembers.value = [];
    clearInvitationToken();
    localStorage.removeItem(ACTIVE_ORGANIZATION_STORAGE_KEY);
    notice.value = t("console.notice.signed_out");
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

onMounted(async () => {
  if (invitationToken.value) {
    loginOpen.value = true;
  }
  try {
    await consoleApi<{ authenticated: boolean }>("/api/v1/auth/session");
    authenticated.value = true;
    await Promise.all([loadOrganizations(), loadBrowserSessions(), loadLoginIdentities()]);
    await acceptInvitationIfPresent();
  } catch {
    // A missing session is the normal first-visit state.
  }
});

async function linkExternalIdentity(provider: "discord" | "twitch") {
  busy.value = true;
  notice.value = "";
  try {
    const authorization = await consoleApi<{ authorization_url: string }>(
      `/api/v1/identity-links/${provider}/authorizations`,
      { method: "POST" },
    );
    window.location.assign(authorization.authorization_url);
  } catch (error) {
    notice.value = messageFor(error);
    busy.value = false;
  }
}

async function linkDiscord() {
  await linkExternalIdentity("discord");
}

async function linkTwitch() {
  await linkExternalIdentity("twitch");
}

async function loadBrowserSessions() {
  if (!authenticated.value) return;
  busy.value = true;
  notice.value = "";
  try {
    const payload = await consoleApi<{ items: BrowserSession[] }>("/api/v1/auth/sessions");
    browserSessions.value = payload.items;
  } catch (error) {
    browserSessions.value = [];
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function refreshSecurity() {
  await Promise.all([loadBrowserSessions(), loadLoginIdentities()]);
}

async function revokeCurrentSession() {
  await signOut();
}

async function revokeAllSessions() {
  busy.value = true;
  notice.value = "";
  try {
    const payload = await consoleApi<{ revoked_count: number }>("/api/v1/auth/sessions", {
      method: "DELETE",
    });
    authenticated.value = false;
    browserSessions.value = [];
    loginIdentities.value = [];
    currentPassword.value = "";
    reauthenticationPassword.value = "";
    newPassword.value = "";
    confirmNewPassword.value = "";
    organizations.value = [];
    organizationInvitations.value = [];
    selectedOrganizationId.value = "";
    clearInvitationToken();
    resetOrganizationWorkspace();
    localStorage.removeItem(ACTIVE_ORGANIZATION_STORAGE_KEY);
    notice.value = t("console.notice.sessions_revoked", { count: payload.revoked_count });
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadLoginIdentities() {
  if (!authenticated.value) return;
  busy.value = true;
  notice.value = "";
  try {
    const payload = await consoleApi<{ items: LoginIdentity[] }>("/api/v1/auth/identities");
    loginIdentities.value = payload.items;
  } catch (error) {
    loginIdentities.value = [];
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function unlinkLoginIdentity(identity: LoginIdentity) {
  busy.value = true;
  notice.value = "";
  try {
    await consoleApi<LoginIdentity>(
      `/api/v1/auth/identities/${encodeURIComponent(identity.id)}`,
      { method: "DELETE" },
    );
    loginIdentities.value = loginIdentities.value.filter((item) => item.id !== identity.id);
    notice.value = t("console.notice.identity_unlinked", {
      provider: providerLabel(identity.provider),
    });
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function changePassword() {
  const validationMessage = passwordChangeValidationMessage({
    currentPassword: currentPassword.value,
    newPassword: newPassword.value,
    confirmNewPassword: confirmNewPassword.value,
  });
  if (validationMessage) {
    notice.value = validationMessage;
    return;
  }
  busy.value = true;
  notice.value = "";
  try {
    await consoleApi<void>("/api/v1/auth/password", {
      method: "PUT",
      body: JSON.stringify({
        current_password: currentPassword.value,
        new_password: newPassword.value,
      }),
    });
    currentPassword.value = "";
    newPassword.value = "";
    confirmNewPassword.value = "";
    notice.value = t("console.notice.password_changed");
    await loadBrowserSessions();
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function refreshRecentAuthentication() {
  if (!reauthenticationPassword.value) {
    notice.value = t("console.notice.enter_password");
    return;
  }
  busy.value = true;
  notice.value = "";
  try {
    await consoleApi<void>("/api/v1/auth/session/reauthentications", {
      method: "POST",
      body: JSON.stringify({ current_password: reauthenticationPassword.value }),
    });
    reauthenticationPassword.value = "";
    notice.value = t("console.notice.recent_auth_refreshed");
    await loadBrowserSessions();
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

function formatSessionTime(value: string | null): string {
  return formatSecurityTimestamp(value);
}

async function loadOrganizations(preferredOrganizationId = selectedOrganizationId.value) {
  busy.value = true;
  notice.value = "";
  try {
    const payload = await consoleApi<{ items: OrganizationListItem[] }>("/api/v1/organizations");
    organizations.value = payload.items;
    selectedOrganizationId.value = chooseActiveOrganizationId(
      payload.items,
      preferredOrganizationId,
    );
    persistActiveOrganization();
    await refreshOrganizationWorkspace();
  } catch (error) {
    organizations.value = [];
    selectedOrganizationId.value = "";
    resetOrganizationWorkspace();
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function selectOrganization() {
  persistActiveOrganization();
  await refreshOrganizationWorkspace();
}

async function refreshOrganizationWorkspace() {
  resetOrganizationWorkspace();
  if (!activeOrganizationId.value) return;
  await Promise.all([
    loadConnections(),
    loadOrganizationMembers(),
    loadOrganizationInvitations(),
  ]);
}

function persistActiveOrganization() {
  persistActiveOrganizationId(localStorage, selectedOrganizationId.value);
}

function resetOrganizationWorkspace() {
  connections.value = [];
  organizationMembers.value = [];
  organizationInvitations.value = [];
  platformHealth.value = null;
  controlModules.value = [];
  dashboardSummary.value = null;
  channelCatalog.value = null;
  botSettings.value = null;
  integrations.value = null;
  serverStatistics.value = null;
  auditTimeline.value = null;
  welcomeSettings.value = null;
  channelPurposes.value = null;
  aiModerationSummary.value = null;
  aiModerationPolicy.value = null;
  auditEvents.value = [];
  auditEventsNextCursor.value = null;
  selectedConnectionId.value = "";
  selectedDiscordConnectionId.value = "";
}

async function createOrganization() {
  busy.value = true;
  notice.value = "";
  try {
    const organization = await consoleApi<Organization>("/api/v1/organizations", {
      method: "POST",
      body: JSON.stringify({ name: organizationName.value }),
    });
    organizationName.value = "";
    await loadOrganizations(organization.id);
    notice.value = t("console.notice.organization_ready", {
      name: organization.name,
      slug: organization.slug,
    });
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadConnections() {
  if (!activeOrganizationId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    const payload = await consoleApi<{ items: PlatformConnection[] }>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections`,
    );
    connections.value = payload.items;
    platformHealth.value = null;
    controlModules.value = [];
    dashboardSummary.value = null;
    channelCatalog.value = null;
    botSettings.value = null;
    integrations.value = null;
    welcomeSettings.value = null;
    channelPurposes.value = null;
    aiModerationSummary.value = null;
    aiModerationPolicy.value = null;
    auditEvents.value = [];
    auditEventsNextCursor.value = null;
    selectedConnectionId.value = usableConnections.value[0]?.id ?? "";
    selectedDiscordConnectionId.value = usableDiscordConnections.value[0]?.id ?? "";
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadOrganizationMembers() {
  if (!activeOrganizationId.value || !canManageOrganizationMembers.value) {
    organizationMembers.value = [];
    return;
  }
  busy.value = true;
  notice.value = "";
  try {
    const payload = await consoleApi<{ items: OrganizationMembership[] }>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/members`,
    );
    organizationMembers.value = payload.items;
  } catch (error) {
    organizationMembers.value = [];
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadOrganizationInvitations() {
  if (!activeOrganizationId.value || !canManageOrganizationMembers.value) {
    organizationInvitations.value = [];
    return;
  }
  busy.value = true;
  notice.value = "";
  try {
    const payload = await consoleApi<{ items: OrganizationInvitation[] }>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/member-invitations`,
    );
    organizationInvitations.value = payload.items;
  } catch (error) {
    organizationInvitations.value = [];
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function addOrganizationMember() {
  if (!activeOrganizationId.value || !newMemberEmail.value.trim()) return;
  normalizeNewMemberScopes();
  busy.value = true;
  notice.value = "";
  try {
    const invitation = await consoleApi<OrganizationInvitation>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/member-invitations`,
      {
        method: "POST",
        body: JSON.stringify({
          email: newMemberEmail.value.trim(),
          role: newMemberRole.value,
          resource_scopes: newMemberScopes.value,
        }),
      },
    );
    organizationInvitations.value = [invitation, ...organizationInvitations.value];
    newMemberEmail.value = "";
    newMemberRole.value = "viewer";
    newMemberScopes.value = [{ resource: "console.control_modules", action: "read" }];
    notice.value =
      invitation.delivery_status === "sent"
        ? t("console.notice.member_invited")
        : t("console.notice.member_invitation_delivery_unavailable");
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function revokeOrganizationInvitation(invitation: OrganizationInvitation) {
  if (!activeOrganizationId.value || invitation.status !== "pending") return;
  busy.value = true;
  notice.value = "";
  try {
    await consoleApi<void>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/member-invitations/${encodeURIComponent(invitation.id)}`,
      { method: "DELETE" },
    );
    organizationInvitations.value = organizationInvitations.value.map((current) =>
      current.id === invitation.id
        ? { ...current, status: "revoked", revoked_at: new Date().toISOString() }
        : current,
    );
    notice.value = t("console.notice.member_invitation_revoked");
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function saveOrganizationMember(member: OrganizationMembership) {
  if (!activeOrganizationId.value) return;
  normalizeMemberScopes(member);
  busy.value = true;
  notice.value = "";
  try {
    const updated = await consoleApi<OrganizationMembership>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/members/${encodeURIComponent(member.user_id)}`,
      {
        method: "PUT",
        body: JSON.stringify({
          role: member.role,
          resource_scopes: member.resource_scopes.map((scope) => ({
            resource: scope.resource,
            action: scope.action,
          })),
        }),
      },
    );
    organizationMembers.value = organizationMembers.value.map((current) =>
      current.user_id === updated.user_id ? updated : current,
    );
    notice.value = t("console.notice.member_updated");
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function removeOrganizationMember(member: OrganizationMembership) {
  if (!activeOrganizationId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    await consoleApi<void>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/members/${encodeURIComponent(member.user_id)}`,
      { method: "DELETE" },
    );
    organizationMembers.value = organizationMembers.value.filter(
      (current) => current.user_id !== member.user_id,
    );
    notice.value = t("console.notice.member_removed");
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

function isNewMemberScopeSelected(scope: MembershipScopeInput): boolean {
  return newMemberScopes.value.some((item) => sameScope(item, scope));
}

function toggleNewMemberScope(scope: MembershipScopeInput) {
  newMemberScopes.value = isNewMemberScopeSelected(scope)
    ? newMemberScopes.value.filter((item) => !sameScope(item, scope))
    : [...newMemberScopes.value, scope];
}

function normalizeNewMemberScopes() {
  newMemberScopes.value = supportedMemberScopesForRole(
    newMemberRole.value,
    newMemberScopes.value,
  );
}

function memberHasScope(member: OrganizationMembership, scope: MembershipScopeInput): boolean {
  return member.resource_scopes.some((item) => sameScope(item, scope));
}

function memberScopeOptionsForRole(role: OrganizationRole): MembershipScopeInput[] {
  return supportedMemberScopesForRole(role, memberScopeOptions);
}

function normalizeMemberScopes(member: OrganizationMembership) {
  member.resource_scopes = supportedMemberScopesForRole(member.role, member.resource_scopes);
}

function canEditOrganizationMember(member: OrganizationMembership): boolean {
  if (member.role === "owner") return false;
  if (activeOrganization.value?.membership.role === "owner") return true;
  return ["moderator", "analyst", "viewer"].includes(member.role);
}

async function toggleMemberScope(member: OrganizationMembership, scope: MembershipScopeInput) {
  member.resource_scopes = memberHasScope(member, scope)
    ? member.resource_scopes.filter((item) => !sameScope(item, scope))
    : [...member.resource_scopes, { id: null, ...scope }];
  await saveOrganizationMember(member);
}

function sameScope(left: MembershipScopeInput, right: MembershipScopeInput): boolean {
  return left.resource === right.resource && left.action === right.action;
}

function scopeLabel(scope: MembershipScopeInput): string {
  return `${t(`console.scope.${scope.resource.replace("console.", "")}`)} · ${t(`console.scope_action.${scope.action}`)}`;
}

function roleLabel(role: OrganizationRole): string {
  return t(`console.roles.${role}`);
}

function memberDisplayLabel(member: OrganizationMembership): string {
  return (
    member.display_name?.trim() ||
    t("console.members.member_fallback", { value: member.user_id.slice(0, 8) })
  );
}

function invitationStatusLabel(status: OrganizationInvitation["status"]): string {
  return t(`console.invitation_status.${status}`);
}

function clearInvitationToken() {
  invitationToken.value = "";
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  url.searchParams.delete("token");
  window.history.replaceState(
    window.history.state,
    document.title,
    `${url.pathname}${url.search}${url.hash}`,
  );
}

async function acceptInvitationIfPresent() {
  if (authenticated.value && invitationToken.value) {
    await acceptOrganizationInvitation();
  }
}

async function acceptOrganizationInvitation() {
  if (!authenticated.value || !invitationToken.value) return;
  busy.value = true;
  notice.value = "";
  try {
    const membership = await consoleApi<OrganizationMembership>(
      "/api/v1/member-invitations/accept",
      {
        method: "POST",
        body: JSON.stringify({ token: invitationToken.value }),
      },
    );
    clearInvitationToken();
    await loadOrganizations(membership.organization_id);
    notice.value = t("console.notice.member_invitation_accepted");
  } catch (error) {
    if (error instanceof ConsoleApiError && error.status === 403) {
      notice.value = t("console.notice.member_invitation_invalid");
    } else {
      notice.value = messageFor(error);
    }
  } finally {
    busy.value = false;
  }
}

function providerLabel(provider: LoginIdentity["provider"]): string {
  return provider === "email" ? t("console.security.email_password") : provider;
}

function identityProtectionLabel(identity: LoginIdentity): string {
  return identity.can_unlink
    ? t("console.security.identity_can_unlink")
    : t("console.security.identity_protected");
}

function identityActionLabel(identity: LoginIdentity): string {
  return identity.can_unlink
    ? t("console.security.unlink")
    : t("console.security.protected");
}

function sessionBulkRevocationLabel(): string {
  return canRevokeAllBrowserSessions.value
    ? t("console.security.bulk_ready")
    : t("console.security.bulk_requires_recent_auth");
}

function connectionStatusLabel(status: PlatformConnection["status"]): string {
  return t(`console.connection_status.${status}`);
}

function platformLabel(platformName: "discord" | "twitch" | "telegram"): string {
  return t(`console.platform_name.${platformName}`);
}

function scopeStatusLabel(status: PlatformConnectionGrantedScope["status"]): string {
  return t(`console.scope_status.${status}`);
}

function moduleStatusLabel(status: ControlModule["status"]): string {
  return t(`console.module_status.${status}`);
}

function capabilityLabel(capability: ControlModule["capability"]): string {
  return t(`console.capability.${capability}`);
}

function signalStatusLabel(status: PlatformHealthSignal["status"]): string {
  return t(`console.signal_status.${status}`);
}

function channelKindLabel(kind: PlatformChannel["kind"]): string {
  return t(`console.channel_kind.${kind}`);
}

function purposeLabel(purpose: string): string {
  const knownPurposes = new Set([
    "welcome",
    "member_log",
    "mod_log",
    "message_log",
    "channel_log",
    "stream_announce",
    "dev_blog",
    "ai_moderation_log",
  ]);
  return knownPurposes.has(purpose) ? t(`console.purpose.${purpose}`) : purpose;
}

function formatLatency(value: number | null): string {
  return value === null ? t("console.platform.unavailable") : `${value} ms`;
}

function formatSeconds(value: number): string {
  return t("console.time.seconds", { value });
}

function connectionStatusDescription(status: PlatformConnection["status"]): string {
  const descriptions: Record<PlatformConnection["status"], string> = {
    pending: t("console.connection_status_description.pending"),
    active: t("console.connection_status_description.active"),
    degraded: t("console.connection_status_description.degraded"),
    reauth_required: t("console.connection_status_description.reauth_required"),
    disconnected: t("console.connection_status_description.disconnected"),
  };
  return descriptions[status];
}

function connectionRiskyActionsBlocked(status: PlatformConnection["status"]): boolean {
  return ["degraded", "reauth_required", "disconnected"].includes(status);
}

function selectConnectionWizard(nextPlatform: ConnectablePlatform) {
  platform.value = nextPlatform;
  externalResourceId.value = "";
}

async function loadControlModules() {
  if (!activeOrganizationId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    const payload = await consoleApi<{ items: ControlModule[] }>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/control-modules`,
    );
    controlModules.value = payload.items;
  } catch (error) {
    controlModules.value = [];
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadPlatformDashboard() {
  if (!activeOrganizationId.value || !selectedConnectionId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    dashboardSummary.value = await consoleApi<PlatformDashboardSummary>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections/${encodeURIComponent(selectedConnectionId.value)}/dashboard`,
    );
  } catch (error) {
    dashboardSummary.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadPlatformChannels() {
  if (!activeOrganizationId.value || !selectedConnectionId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    channelCatalog.value = await consoleApi<PlatformChannelCatalog>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections/${encodeURIComponent(selectedConnectionId.value)}/channels`,
    );
  } catch (error) {
    channelCatalog.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadPlatformBotSettings() {
  if (!activeOrganizationId.value || !selectedConnectionId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    botSettings.value = await consoleApi<PlatformBotSettings>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections/${encodeURIComponent(selectedConnectionId.value)}/bot-settings`,
    );
  } catch (error) {
    botSettings.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadPlatformIntegrations() {
  if (!activeOrganizationId.value || !selectedConnectionId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    integrations.value = await consoleApi<PlatformIntegrations>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections/${encodeURIComponent(selectedConnectionId.value)}/integrations`,
    );
  } catch (error) {
    integrations.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadPlatformServerStatistics() {
  if (!activeOrganizationId.value || !selectedConnectionId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    serverStatistics.value = await consoleApi<PlatformServerStatistics>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections/${encodeURIComponent(selectedConnectionId.value)}/server-statistics`,
    );
  } catch (error) {
    serverStatistics.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadPlatformAuditTimeline() {
  if (!activeOrganizationId.value || !selectedConnectionId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    auditTimeline.value = await consoleApi<PlatformAuditTimeline>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections/${encodeURIComponent(selectedConnectionId.value)}/audit-timeline`,
    );
  } catch (error) {
    auditTimeline.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

function selectPlatformConnection() {
  dashboardSummary.value = null;
  channelCatalog.value = null;
  botSettings.value = null;
  integrations.value = null;
  platformHealth.value = null;
}

async function loadDiscordDashboard() {
  if (!activeOrganizationId.value || !selectedDiscordConnectionId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    dashboardSummary.value = await consoleApi<PlatformDashboardSummary>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections/${encodeURIComponent(selectedDiscordConnectionId.value)}/dashboard`,
    );
  } catch (error) {
    dashboardSummary.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadOrganizationAuditEvents(nextPage = false) {
  if (!activeOrganizationId.value) return;
  if (nextPage && !auditEventsNextCursor.value) return;
  busy.value = true;
  notice.value = "";
  try {
    const query = nextPage ? `?after=${encodeURIComponent(auditEventsNextCursor.value ?? "")}` : "";
    const page = await consoleApi<AuditEventPage>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/audit-events${query}`,
    );
    auditEvents.value = nextPage ? [...auditEvents.value, ...page.items] : page.items;
    auditEventsNextCursor.value = page.next_cursor;
  } catch (error) {
    if (!nextPage) auditEvents.value = [];
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadDiscordChannels() {
  if (!activeOrganizationId.value || !selectedDiscordConnectionId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    channelCatalog.value = await consoleApi<PlatformChannelCatalog>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections/${encodeURIComponent(selectedDiscordConnectionId.value)}/channels`,
    );
  } catch (error) {
    channelCatalog.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadDiscordChannelPurposes() {
  if (!activeOrganizationId.value || !selectedDiscordConnectionId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    channelPurposes.value = await consoleApi<PlatformChannelPurposes>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections/${encodeURIComponent(selectedDiscordConnectionId.value)}/channel-purposes`,
    );
  } catch (error) {
    channelPurposes.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadDiscordAiModerationSummary() {
  if (!activeOrganizationId.value || !selectedDiscordConnectionId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    aiModerationSummary.value = await consoleApi<PlatformAiModerationSummary>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections/${encodeURIComponent(selectedDiscordConnectionId.value)}/ai-moderation-summary`,
    );
  } catch (error) {
    aiModerationSummary.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadDiscordAiModerationPolicy() {
  if (!activeOrganizationId.value || !selectedDiscordConnectionId.value || !canRunSelectedDiscordWrites.value) return;
  busy.value = true;
  notice.value = "";
  try {
    const state = await consoleApi<PlatformAiModerationPolicyState>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections/${encodeURIComponent(selectedDiscordConnectionId.value)}/ai-moderation-policy`,
    );
    aiModerationPolicy.value = state;
    aiModerationBlacklistWords.value = state.policy.blacklist_words.join("\n");
    aiModerationAllowedDomains.value = state.policy.allowed_domains.join("\n");
  } catch (error) {
    aiModerationPolicy.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function saveDiscordAiModerationPolicy() {
  if (!activeOrganizationId.value || !selectedDiscordConnectionId.value || !aiModerationPolicy.value || !canRunSelectedDiscordWrites.value) return;
  busy.value = true;
  notice.value = "";
  try {
    const policy = {
      ...aiModerationPolicy.value.policy,
      blacklist_words: splitPolicyValues(aiModerationBlacklistWords.value),
      allowed_domains: splitPolicyValues(aiModerationAllowedDomains.value),
    };
    aiModerationSummary.value = await consoleApi<PlatformAiModerationSummary>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections/${encodeURIComponent(selectedDiscordConnectionId.value)}/ai-moderation-policy`,
      { method: "PUT", body: JSON.stringify(policy) },
    );
    aiModerationPolicy.value = { ...aiModerationPolicy.value, policy, is_default_policy: false };
    notice.value = t("console.notice.policy_saved");
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

function splitPolicyValues(value: string): string[] {
  return [...new Set(value.split(/[\n,]/).map((item) => item.trim()).filter(Boolean))];
}

async function saveDiscordChannelPurpose() {
  if (!activeOrganizationId.value || !selectedDiscordConnectionId.value || !selectedPurposeChannelId.value || !canRunSelectedDiscordWrites.value) return;
  busy.value = true;
  notice.value = "";
  try {
    channelPurposes.value = await consoleApi<PlatformChannelPurposes>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections/${encodeURIComponent(selectedDiscordConnectionId.value)}/channel-purposes`,
      { method: "PUT", body: JSON.stringify({ purpose: selectedPurpose.value, channel_id: selectedPurposeChannelId.value }) },
    );
    notice.value = t("console.notice.purpose_saved");
  } catch (error) { notice.value = messageFor(error); } finally { busy.value = false; }
}

async function loadDiscordWelcomeSettings() {
  if (!activeOrganizationId.value || !selectedDiscordConnectionId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    welcomeSettings.value = await consoleApi<PlatformWelcomeSettings>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections/${encodeURIComponent(selectedDiscordConnectionId.value)}/welcome-settings`,
    );
  } catch (error) {
    welcomeSettings.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function saveDiscordWelcomeSettings() {
  if (!activeOrganizationId.value || !selectedDiscordConnectionId.value || !welcomeSettings.value || !canRunSelectedDiscordWrites.value) return;
  busy.value = true;
  notice.value = "";
  try {
    const settings = welcomeSettings.value;
    welcomeSettings.value = await consoleApi<PlatformWelcomeSettings>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections/${encodeURIComponent(selectedDiscordConnectionId.value)}/welcome-settings`,
      {
        method: "PUT",
        body: JSON.stringify({
          title: settings.title,
          description: settings.description,
          thumbnail_url: settings.thumbnail_url,
          footer_text: settings.footer_text,
          footer_icon_url: settings.footer_icon_url,
          color: settings.color,
          is_enabled: settings.is_enabled,
          rules_channel_id: settings.rules_channel_id?.trim() || null,
          roles_channel_id: settings.roles_channel_id?.trim() || null,
        }),
      },
    );
    notice.value = t("console.notice.welcome_saved");
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

function selectDiscordConnection() {
  dashboardSummary.value = null;
  channelCatalog.value = null;
  welcomeSettings.value = null;
  channelPurposes.value = null;
  aiModerationSummary.value = null;
  aiModerationPolicy.value = null;
  auditEvents.value = [];
  auditEventsNextCursor.value = null;
}

async function loadPlatformHealth() {
  if (!activeOrganizationId.value || !selectedConnection.value) return;
  busy.value = true;
  notice.value = "";
  try {
    platformHealth.value = await consoleApi<PlatformHealth>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platforms/${selectedConnection.value.platform}/health`,
    );
  } catch (error) {
    platformHealth.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function registerConnection() {
  if (!activeOrganizationId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    const connection = await consoleApi<PlatformConnection>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections`,
      {
        method: "POST",
        body: JSON.stringify({ platform: platform.value, external_resource_id: externalResourceId.value }),
      },
    );
    externalResourceId.value = "";
    connections.value = [connection, ...connections.value];
    notice.value = t("console.notice.connection_pending", {
      platform: platformLabel(connection.platform),
    });
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function runConnectionLifecycle(
  connection: PlatformConnection,
  action: "reauthorize" | "revoke" | "disconnect",
) {
  if (!activeOrganizationId.value) return;
  const suffix =
    action === "reauthorize"
      ? "reauthorizations"
      : action === "revoke"
        ? "revocations"
        : "";
  const path =
    action === "disconnect"
      ? `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections/${encodeURIComponent(connection.id)}`
      : `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections/${encodeURIComponent(connection.id)}/${suffix}`;
  busy.value = true;
  notice.value = "";
  try {
    const updated = await consoleApi<PlatformConnection>(path, {
      method: action === "disconnect" ? "DELETE" : "POST",
      headers: { "Idempotency-Key": `${action}:${connection.id}` },
    });
    connections.value = connections.value.map((item) =>
      item.id === updated.id ? updated : item,
    );
    selectPlatformConnection();
    selectDiscordConnection();
    notice.value = t("console.notice.connection_state", {
      platform: platformLabel(updated.platform),
      status: connectionStatusLabel(updated.status),
    });
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

function messageFor(error: unknown): string {
  if (error instanceof ConsoleApiError && error.status === 401) {
    return t("console.error.invalid_credentials");
  }
  if (error instanceof ConsoleApiError && error.status === 403) {
    return t("console.error.forbidden");
  }
  return t("console.error.unavailable");
}
</script>

<template>
  <div :class="['muxivo-app', `theme-${theme}`, 'console-app', { 'console-authenticated': authenticated }]">
    <template v-if="!authenticated">
      <header class="app-header console-public-header">
        <a class="wordmark" href="#top" :aria-label="t('header.home')" @click.prevent="landingTab = 'overview'">
          <img class="wordmark-logo" src="/muxivo-logo.png" alt="" />
          <span>
            <span class="wordmark-main">MUXIVO</span>
            <span class="wordmark-sub">{{ t("header.discord_bot") }}</span>
          </span>
        </a>

        <nav class="public-nav" :aria-label="t('header.primary_navigation')">
          <button
            v-for="item in publicNavItems"
            :key="item.key"
            class="animated-nav-link public-nav-button"
            :class="{ active: landingTab === item.key }"
            type="button"
            @click="landingTab = item.key"
          >
            <span
              v-for="(letter, index) in navLetters(item.label)"
              :key="`${item.key}-${letter}-${index}`"
              class="animated-nav-link-letter"
              :style="{ transitionDelay: `${index * 22}ms` }"
            >
              {{ letter === " " ? "\u00a0" : letter }}
            </span>
          </button>
        </nav>

        <div class="header-actions">
          <LanguageSwitcher />
          <button
            class="icon-button theme-toggle"
            type="button"
            :title="theme === 'dark' ? t('common.theme_to_light') : t('common.theme_to_dark')"
            :aria-label="theme === 'dark' ? t('common.theme_to_light') : t('common.theme_to_dark')"
            @click="toggleTheme"
          >
            <Sun v-if="theme === 'dark'" :size="18" aria-hidden="true" />
            <Moon v-else :size="18" aria-hidden="true" />
          </button>
          <button class="panel-cta" type="button" @click="loginOpen = true">
            {{ t("header.see_panel") }}
          </button>
        </div>
      </header>

      <MuxivoLanding v-if="landingTab === 'overview'" id="top" />
      <GetToKnowUs v-else id="top" />
      <PublicFooter />
      <section
        v-if="loginOpen"
        class="login-overlay"
        role="dialog"
        aria-modal="true"
        :aria-label="t('console.auth.dialog_label')"
        @keydown.esc="loginOpen = false"
      >
        <div class="login-panel">
          <button
            class="close-login"
            type="button"
            :aria-label="t('console.auth.close')"
            @click="loginOpen = false"
          >
            ×
          </button>
          <span class="eyebrow">MUXIVO CONSOLE</span>
          <h2>
            {{
              authMode === "sign-in"
                ? t("console.auth.welcome_title")
                : t("console.auth.create_title")
            }}
          </h2>
          <p>
            {{
              authMode === "sign-in"
                ? t("console.auth.sign_in_description")
                : t("console.auth.create_description")
            }}
          </p>
          <div v-if="invitationToken" class="auth-invitation-context" role="status">
            <strong>{{ t("console.invitation.accept_title") }}</strong>
            <p>{{ t("console.invitation.accept_description") }}</p>
          </div>
          <div class="auth-mode-tabs" role="tablist" :aria-label="t('console.auth.mode_label')">
            <button
              type="button"
              role="tab"
              :aria-selected="authMode === 'sign-in'"
              :class="{ active: authMode === 'sign-in' }"
              @click="authMode = 'sign-in'"
            >
              {{ t("console.auth.sign_in") }}
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="authMode === 'create-account'"
              :class="{ active: authMode === 'create-account' }"
              @click="authMode = 'create-account'"
            >
              {{ t("console.auth.create_account") }}
            </button>
          </div>
          <form v-if="authMode === 'sign-in'" @submit.prevent="signIn">
            <label>
              {{ t("console.auth.email") }}
              <input v-model="email" type="email" autocomplete="email" required />
            </label>
            <label>
              {{ t("console.auth.password") }}
              <input
                v-model="password"
                type="password"
                autocomplete="current-password"
                minlength="12"
                required
              />
            </label>
            <button :disabled="busy">
              {{ busy ? t("console.auth.signing_in") : t("console.auth.sign_in_button") }}
            </button>
          </form>
          <form v-else @submit.prevent="createAccount">
            <label>
              {{ t("console.auth.display_name") }}
              <input
                v-model="registrationDisplayName"
                autocomplete="name"
                maxlength="64"
                required
              />
            </label>
            <label>
              {{ t("console.auth.email") }}
              <input v-model="registrationEmail" type="email" autocomplete="email" required />
            </label>
            <label>
              {{ t("console.auth.password") }}
              <input
                v-model="registrationPassword"
                type="password"
                autocomplete="new-password"
                minlength="12"
                maxlength="1024"
                required
              />
            </label>
            <button :disabled="busy">
              {{ busy ? t("console.auth.creating") : t("console.auth.create_button") }}
            </button>
          </form>
          <div class="identity-link">
            <h3>{{ t("console.auth.discord_heading") }}</h3>
            <p>{{ t("console.auth.discord_description") }}</p>
            <button type="button" :disabled="busy" @click="signInWithDiscord">
              {{ t("console.auth.discord_button") }}
            </button>
          </div>
          <div class="identity-link">
            <h3>{{ t("console.auth.recovery_heading") }}</h3>
            <p>
              {{ t("console.auth.recovery_description") }}
            </p>
            <form @submit.prevent="requestPasswordRecovery">
              <label>
                {{ t("console.auth.account_email") }}
                <input
                  v-model="recoveryEmail"
                  type="email"
                  autocomplete="email"
                  :placeholder="t('console.auth.email_placeholder')"
                  required
                />
              </label>
              <button type="submit" :disabled="busy">
                {{ busy ? t("console.auth.requesting") : t("console.auth.request_reset") }}
              </button>
            </form>
            <form @submit.prevent="completePasswordRecovery">
              <label>
                {{ t("console.auth.recovery_token") }}
                <input v-model="recoveryToken" autocomplete="one-time-code" required />
              </label>
              <label>
                {{ t("console.auth.new_password") }}
                <input
                  v-model="recoveryNewPassword"
                  type="password"
                  autocomplete="new-password"
                  minlength="12"
                  maxlength="1024"
                  required
                />
              </label>
              <label>
                {{ t("console.auth.confirm_password") }}
                <input
                  v-model="recoveryConfirmPassword"
                  type="password"
                  autocomplete="new-password"
                  minlength="12"
                  maxlength="1024"
                  required
                />
              </label>
              <button type="submit" :disabled="busy">
                {{ busy ? t("console.auth.resetting") : t("console.auth.reset_password") }}
              </button>
            </form>
          </div>
        </div>
      </section>
    </template>
    <section v-else class="console-shell">
      <aside class="console-sidebar" :aria-label="t('console.sidebar.navigation')">
        <div class="console-sidebar-header">
          <a class="console-brand" href="#console-overview" @click.prevent="scrollToConsoleSection('overview')">
            <img class="console-brand-logo" src="/muxivo-logo.png" alt="" />
            <span>
              <strong>MUXIVO</strong>
              <small>{{ t("console.brand_subtitle") }}</small>
            </span>
          </a>
          <span class="console-product-pill">{{ t("console.product_label") }}</span>
        </div>

        <div class="console-organization-picker">
          <label for="console-organization-select">{{ t("console.organization.label") }}</label>
          <select
            id="console-organization-select"
            v-model="selectedOrganizationId"
            :disabled="busy || !organizations.length"
            @change="selectOrganization"
          >
            <option v-if="!organizations.length" value="" disabled>
              {{ t("console.organization.empty_select") }}
            </option>
            <option
              v-for="item in organizations"
              :key="item.organization.id"
              :value="item.organization.id"
            >
              {{ item.organization.name }} · {{ roleLabel(item.membership.role) }}
            </option>
          </select>
          <p v-if="activeOrganization" class="console-active-organization">
            <span class="console-status-dot" aria-hidden="true"></span>
            {{ t("console.organization.active") }}: {{ activeOrganization.organization.slug }}
          </p>
          <p v-else class="console-empty-organization">
            {{ t("console.organization.empty_help") }}
          </p>
        </div>

        <nav class="console-sidebar-nav" :aria-label="t('console.sidebar.sections')">
          <button
            v-for="item in consoleNavItems"
            :key="item.key"
            type="button"
            class="console-nav-item"
            :class="{ active: activeConsoleSection === item.key }"
            :aria-current="activeConsoleSection === item.key ? 'page' : undefined"
            @click="scrollToConsoleSection(item.key)"
          >
            <component :is="item.icon" :size="17" aria-hidden="true" />
            <span>{{ item.label }}</span>
          </button>
        </nav>

        <div class="console-sidebar-footer">
          <button
            class="console-utility-button"
            type="button"
            :title="theme === 'dark' ? t('common.theme_to_light') : t('common.theme_to_dark')"
            @click="toggleTheme"
          >
            <Sun v-if="theme === 'dark'" :size="16" aria-hidden="true" />
            <Moon v-else :size="16" aria-hidden="true" />
            <span>{{ theme === "dark" ? t("console.theme.light") : t("console.theme.dark") }}</span>
          </button>
          <div class="console-sidebar-actions">
            <LanguageSwitcher />
            <button class="console-utility-button console-sign-out" type="button" :disabled="busy" @click="signOut">
              <LogOut :size="16" aria-hidden="true" />
              <span>{{ t("console.shell.sign_out") }}</span>
            </button>
          </div>
        </div>
      </aside>

      <div class="console-shell-main">
        <header class="console-topbar">
          <div class="console-topbar-copy">
            <span class="eyebrow">{{ t("console.product_label") }}</span>
            <h1>{{ activeConsoleNavItem.label }}</h1>
            <p>{{ activeConsoleNavItem.description }}</p>
          </div>
          <div class="console-topbar-actions">
            <span class="console-session-state">
              <span class="console-status-dot" aria-hidden="true"></span>
              {{ t("console.shell.session_active") }}
            </span>
            <LanguageSwitcher />
            <button
              class="icon-button theme-toggle"
              type="button"
              :title="theme === 'dark' ? t('common.theme_to_light') : t('common.theme_to_dark')"
              :aria-label="theme === 'dark' ? t('common.theme_to_light') : t('common.theme_to_dark')"
              @click="toggleTheme"
            >
              <Sun v-if="theme === 'dark'" :size="18" aria-hidden="true" />
              <Moon v-else :size="18" aria-hidden="true" />
            </button>
          </div>
        </header>

        <main class="console-content">
    <section
      v-if="invitationToken"
      class="card invitation-card console-section"
      aria-labelledby="organization-invitation-heading"
    >
      <div class="section-heading">
        <div>
          <span class="eyebrow">{{ t("console.invitation.eyebrow") }}</span>
          <h2 id="organization-invitation-heading">{{ t("console.invitation.accept_title") }}</h2>
          <p>{{ t("console.invitation.accept_description") }}</p>
        </div>
        <button type="button" :disabled="busy" @click="acceptOrganizationInvitation">
          {{ busy ? t("console.members.loading") : t("console.invitation.accept_button") }}
        </button>
      </div>
    </section>
    <section id="console-overview" class="card console-section console-overview-card">
      <div class="section-heading">
        <div>
          <span class="eyebrow">{{ t("console.overview.eyebrow") }}</span>
          <h2>{{ t("console.overview.title") }}</h2>
          <p>{{ t("console.overview.description") }}</p>
        </div>
      </div>
      <h2>{{ t("console.overview.create_title") }}</h2>
      <p>{{ t("console.overview.create_description") }}</p>
      <form @submit.prevent="createOrganization"><label>{{ t("console.overview.name") }}<input v-model="organizationName" maxlength="128" required /></label><button :disabled="busy">{{ busy ? t("console.overview.creating") : t("console.overview.create_button") }}</button></form>
      <div class="identity-provider-grid">
        <div class="identity-link">
          <h3>{{ t("console.overview.discord_identity") }}</h3>
          <p>{{ t("console.overview.discord_description") }}</p>
          <button type="button" :disabled="busy" @click="linkDiscord">{{ t("console.overview.link_discord") }}</button>
        </div>
        <div class="identity-link">
          <h3>{{ t("console.overview.twitch_identity") }}</h3>
          <p>{{ t("console.overview.twitch_description") }}</p>
          <button type="button" :disabled="busy" @click="linkTwitch">{{ t("console.overview.link_twitch") }}</button>
        </div>
      </div>
    </section>
    <section id="console-security" class="card workspace console-section">
      <div class="section-heading">
        <div>
          <h2>{{ t("console.security.title") }}</h2>
          <p>{{ t("console.security.description") }}</p>
        </div>
        <button
          type="button"
          :disabled="busy"
          @click="refreshSecurity"
        >
          {{ busy ? t("console.security.refreshing") : t("console.security.refresh") }}
        </button>
      </div>
      <ul v-if="browserSessions.length" class="health-signals audit-events">
        <li v-for="session in browserSessions" :key="session.id">
          <span>
            <strong>{{ session.device_label }}{{ session.is_current ? ` · ${t("console.security.session_current")}` : "" }}</strong>
            <small>{{ t("console.security.last_seen", { value: formatSessionTime(session.last_seen_at) }) }} · {{ t("console.security.expires", { value: formatSessionTime(session.expires_at) }) }}</small>
            <small>
              {{ session.ip_fingerprint ?? t("console.security.ip_unknown") }} ·
              {{ session.user_agent_fingerprint ?? t("console.security.ua_unknown") }} ·
              {{ session.assurance_level === "recent_authentication" ? t("console.security.assurance_recent") : t("console.security.assurance_password") }}
            </small>
          </span>
          <em :data-status="session.is_current ? 'active' : 'operational'">
            {{ session.is_current ? t("console.security.session_current") : t("console.security.session_active") }}
          </em>
        </li>
      </ul>
      <p v-else-if="!busy">{{ t("console.security.empty_sessions") }}</p>
      <form class="connection-form" @submit.prevent="refreshRecentAuthentication">
        <label>
          {{ t("console.security.recent_auth_label") }}
          <input
            v-model="reauthenticationPassword"
            type="password"
            autocomplete="current-password"
            :placeholder="t('console.security.current_password_placeholder')"
            required
          />
        </label>
        <p>{{ t("console.security.recent_auth_description") }}</p>
        <button :disabled="busy">
          {{ busy ? t("console.security.confirming") : t("console.security.confirm_recent") }}
        </button>
      </form>
      <div class="section-heading policy-heading">
        <div>
          <h3>{{ t("console.security.identities_title") }}</h3>
          <p>{{ t("console.security.identities_description") }}</p>
        </div>
        <button type="button" :disabled="busy" @click="loadLoginIdentities">
          {{ t("console.security.refresh_identities") }}
        </button>
      </div>
      <ul v-if="loginIdentities.length" class="health-signals audit-events">
        <li v-for="identity in loginIdentities" :key="identity.id">
          <span>
            <strong>{{ providerLabel(identity.provider) }}</strong>
            <small>{{ t("console.security.linked", { value: formatSessionTime(identity.linked_at) }) }} · {{ t("console.security.last_used", { value: formatSessionTime(identity.last_used_at) }) }}</small>
            <small>{{ identityProtectionLabel(identity) }}</small>
          </span>
          <button
            type="button"
            :disabled="busy || !identity.can_unlink"
            @click="unlinkLoginIdentity(identity)"
          >
            {{ identityActionLabel(identity) }}
          </button>
        </li>
      </ul>
      <p v-else-if="!busy">{{ t("console.security.empty_identities") }}</p>
      <div class="section-heading policy-heading">
        <div>
          <h3>{{ t("console.security.password_title") }}</h3>
          <p>{{ t("console.security.password_description") }}</p>
        </div>
      </div>
      <form class="connection-form" @submit.prevent="changePassword">
        <label>
          {{ t("console.security.current_password_placeholder") }}
          <input
            v-model="currentPassword"
            type="password"
            autocomplete="current-password"
            required
          />
        </label>
        <label>
          {{ t("console.auth.new_password") }}
          <input
            v-model="newPassword"
            type="password"
            autocomplete="new-password"
            minlength="12"
            maxlength="1024"
            required
          />
        </label>
        <label>
          {{ t("console.auth.confirm_password") }}
          <input
            v-model="confirmNewPassword"
            type="password"
            autocomplete="new-password"
            minlength="12"
            maxlength="1024"
            required
          />
        </label>
        <button type="submit" :disabled="busy">
          {{ busy ? t("console.security.changing") : t("console.security.change_button") }}
        </button>
      </form>
      <div class="connection-form">
        <button type="button" :disabled="busy" @click="revokeCurrentSession">
          {{ t("console.security.revoke_current") }}
        </button>
        <button
          type="button"
          :disabled="busy || !canRevokeAllBrowserSessions"
          @click="revokeAllSessions"
        >
          {{ t("console.security.revoke_all") }}
        </button>
        <p>{{ sessionBulkRevocationLabel() }}</p>
      </div>
    </section>
    <section id="console-connections" class="card workspace console-section">
      <h2>{{ t("console.connections.title") }}</h2>
      <p>{{ t("console.connections.description") }}</p>
      <div v-if="organizations.length" class="identity-link">
        <h3>{{ t("console.connections.active_org_title") }}</h3>
        <label>
          {{ t("console.connections.organization_label") }}
          <select v-model="selectedOrganizationId" @change="selectOrganization">
            <option
              v-for="item in organizations"
              :key="item.organization.id"
              :value="item.organization.id"
            >
              {{ item.organization.name }} · {{ roleLabel(item.membership.role) }}
            </option>
          </select>
        </label>
        <p v-if="activeOrganization">
          {{ t("console.connections.selected_help", { slug: activeOrganization.organization.slug }) }}
        </p>
        <button type="button" :disabled="busy" @click="loadOrganizations()">
          {{ busy ? t("console.security.refreshing") : t("console.connections.refresh_organizations") }}
        </button>
      </div>
      <div v-else class="identity-link">
        <h3>{{ t("console.connections.empty_title") }}</h3>
        <p>{{ t("console.connections.empty_help") }}</p>
      </div>
      <section v-if="activeOrganizationId" class="platform-dashboard" aria-labelledby="connection-wizard-heading">
        <div class="section-heading">
          <div>
            <h3 id="connection-wizard-heading">{{ selectedConnectionWizard.title }}</h3>
            <p>{{ selectedConnectionWizard.summary }}</p>
          </div>
        </div>
        <div class="platform-choice-grid" role="list" :aria-label="t('console.connections.type_aria')">
          <button
            v-for="option in localizedConnectionWizardOptions"
            :key="option.platform"
            type="button"
            :class="{ active: platform === option.platform }"
            :aria-pressed="platform === option.platform"
            @click="selectConnectionWizard(option.platform)"
          >
            <strong>{{ option.title }}</strong>
            <span>{{ option.summary }}</span>
          </button>
        </div>
        <ol class="health-signals">
          <li v-for="step in selectedConnectionWizard.preflightSteps" :key="step">
            <span><strong>{{ step }}</strong></span>
          </li>
        </ol>
        <form class="connection-form" @submit.prevent="registerConnection">
          <label>{{ selectedConnectionWizard.resourceLabel }}<input v-model="externalResourceId" :placeholder="selectedConnectionWizard.resourcePlaceholder" required /></label>
          <p>{{ selectedConnectionWizard.resourceHelp }}</p>
          <p v-if="platform === 'discord'">
            {{ t("console.connections.ownership_discord") }}
            <button type="button" class="inline-action" :disabled="busy" @click="linkDiscord">
              {{ t("console.connections.link_identity", { platform: "Discord" }) }}
            </button>
          </p>
          <p v-else-if="platform === 'twitch'">
            {{ t("console.connections.ownership_twitch") }}
            <button type="button" class="inline-action" :disabled="busy" @click="linkTwitch">
              {{ t("console.connections.link_identity", { platform: "Twitch" }) }}
            </button>
          </p>
          <button :disabled="busy">{{ busy ? t("console.members.loading") : selectedConnectionWizard.actionLabel }}</button>
        </form>
        <p>{{ t("console.connections.security_note") }}</p>
      </section>
      <ul v-if="connections.length" class="connections">
        <li v-for="connection in connections" :key="connection.id">
          <strong>{{ platformLabel(connection.platform) }}</strong>
          <span>
            {{ connection.external_resource_id }}
            <small>{{ connectionStatusDescription(connection.status) }}</small>
          </span>
          <em :data-status="connection.status">{{ connectionStatusLabel(connection.status) }}</em>
          <button type="button" :disabled="busy || connection.status === 'active'" @click="runConnectionLifecycle(connection, 'reauthorize')">{{ t("console.connections.reauthorize") }}</button>
          <button type="button" :disabled="busy || connection.status === 'reauth_required' || connection.status === 'pending' || connection.status === 'disconnected'" @click="runConnectionLifecycle(connection, 'revoke')">{{ t("console.connections.revoke") }}</button>
          <button type="button" :disabled="busy || connection.status === 'disconnected'" @click="runConnectionLifecycle(connection, 'disconnect')">{{ t("console.connections.disconnect") }}</button>
          <small v-if="connectionRiskyActionsBlocked(connection.status)">{{ t("console.connections.risky_blocked") }}</small>
          <ul v-if="connection.granted_scopes.length" class="scope-list" :aria-label="t('console.connections.granted_scopes')">
            <li v-for="scope in connection.granted_scopes" :key="scope.key">
              <span>
                <strong>{{ scope.display_name }}</strong>
                <small>{{ scope.description }}</small>
              </span>
              <em :data-status="scope.status">{{ scopeStatusLabel(scope.status) }}</em>
            </li>
          </ul>
        </li>
      </ul>
      <section id="console-members" v-if="canManageOrganizationMembers" class="platform-dashboard console-section" aria-labelledby="organization-members-heading">
        <div class="section-heading"><div><h3 id="organization-members-heading">{{ t("console.members.title") }}</h3><p>{{ t("console.members.description") }}</p></div><button type="button" :disabled="busy" @click="loadOrganizationMembers">{{ busy ? t("console.members.loading") : t("console.members.load") }}</button></div>
        <form class="connection-form" @submit.prevent="addOrganizationMember">
          <label>{{ t("console.members.email") }}<input v-model="newMemberEmail" type="email" autocomplete="email" :placeholder="t('console.auth.email_placeholder')" required /></label>
          <label>{{ t("console.members.role") }}<select v-model="newMemberRole" @change="normalizeNewMemberScopes"><option v-for="role in availableMemberRoleOptions" :key="role" :value="role">{{ roleLabel(role) }}</option></select></label>
          <fieldset>
            <legend>{{ t("console.members.scopes") }}</legend>
            <label v-for="scope in availableNewMemberScopeOptions" :key="`${scope.resource}-${scope.action}`">
              <input
                type="checkbox"
                :checked="isNewMemberScopeSelected(scope)"
                @change="toggleNewMemberScope(scope)"
              />
              {{ scopeLabel(scope) }}
            </label>
          </fieldset>
          <button :disabled="busy">{{ busy ? t("console.members.inviting") : t("console.members.invite") }}</button>
        </form>
        <div class="section-heading policy-heading">
          <div>
            <h3>{{ t("console.members.invitations_title") }}</h3>
            <p>{{ t("console.members.invitations_description") }}</p>
          </div>
          <button type="button" :disabled="busy" @click="loadOrganizationInvitations">
            {{ busy ? t("console.members.loading") : t("console.members.load_invitations") }}
          </button>
        </div>
        <ul v-if="organizationInvitations.length" class="health-signals invitation-list">
          <li v-for="invitation in organizationInvitations" :key="invitation.id">
            <span>
              <strong>{{ invitation.email_hint }} · {{ roleLabel(invitation.role) }}</strong>
              <small>
                {{ t("console.members.invitation_status", { value: invitationStatusLabel(invitation.status) }) }} ·
                {{ t("console.members.invitation_expires", { value: formatSessionTime(invitation.expires_at) }) }}
              </small>
              <small v-if="invitation.delivery_status === 'unavailable' || invitation.delivery_status === 'failed'">
                {{ t("console.members.invitation_delivery_unavailable") }}
              </small>
            </span>
            <div class="invitation-actions">
              <em :data-status="invitation.status">{{ invitationStatusLabel(invitation.status) }}</em>
              <button
                v-if="invitation.status === 'pending'"
                type="button"
                :disabled="busy"
                @click="revokeOrganizationInvitation(invitation)"
              >
                {{ t("console.members.revoke_invitation") }}
              </button>
            </div>
          </li>
        </ul>
        <p v-else-if="!busy">{{ t("console.members.invitations_empty") }}</p>
        <ul v-if="organizationMembers.length" class="health-signals">
          <li v-for="member in organizationMembers" :key="member.user_id">
            <span>
              <strong>{{ memberDisplayLabel(member) }}</strong>
              <small v-if="member.display_name">
                {{ t("console.members.member_identifier", { value: member.user_id.slice(0, 8) }) }}
              </small>
              <small>{{ t("console.members.member_scopes", { role: roleLabel(member.role), count: member.resource_scopes.length }) }}</small>
            </span>
            <select
              v-if="canEditOrganizationMember(member)"
              v-model="member.role"
              :disabled="busy"
              @change="saveOrganizationMember(member)"
            >
              <option v-for="role in availableMemberRoleOptions" :key="role" :value="role">{{ roleLabel(role) }}</option>
            </select>
            <button v-if="canEditOrganizationMember(member)" type="button" :disabled="busy" @click="removeOrganizationMember(member)">{{ t("console.members.remove") }}</button>
            <div v-if="canEditOrganizationMember(member)" class="connection-form">
              <label v-for="scope in memberScopeOptionsForRole(member.role)" :key="`${member.user_id}-${scope.resource}-${scope.action}`">
                <input
                  type="checkbox"
                  :checked="memberHasScope(member, scope)"
                  :disabled="busy"
                  @change="toggleMemberScope(member, scope)"
                />
                {{ scopeLabel(scope) }}
              </label>
            </div>
          </li>
        </ul>
        <p v-else-if="!busy">{{ t("console.members.empty") }}</p>
      </section>
      <section v-if="activeOrganizationId" class="platform-dashboard" aria-labelledby="control-modules-heading">
        <div class="section-heading"><div><h3 id="control-modules-heading">{{ t("console.modules.title") }}</h3><p>{{ t("console.modules.description") }}</p></div><button type="button" :disabled="busy" @click="loadControlModules">{{ busy ? t("console.members.loading") : t("console.modules.load") }}</button></div>
        <ul v-if="controlModules.length" class="health-signals"><li v-for="module in controlModules" :key="module.key"><span><strong>{{ module.display_name }}</strong><small>{{ platformLabel(module.platform) }} · {{ capabilityLabel(module.capability) }}</small></span><em :data-status="module.status">{{ moduleStatusLabel(module.status) }}</em></li></ul>
      </section>
      <section v-if="usableConnections.length" class="platform-dashboard" aria-labelledby="platform-activity-heading">
        <div class="section-heading"><div><h3 id="platform-activity-heading">{{ t("console.platform_activity.title") }}</h3><p>{{ t("console.platform_activity.description") }}</p></div></div>
        <label class="connection-picker">{{ t("console.platform.connection") }}<select v-model="selectedConnectionId" @change="selectPlatformConnection"><option v-for="connection in usableConnections" :key="connection.id" :value="connection.id">{{ platformLabel(connection.platform) }} · {{ connection.external_resource_id }} · {{ connectionStatusLabel(connection.status) }}</option></select></label>
        <div class="section-heading"><div><h4>{{ t("console.platform.summary") }}</h4><p>{{ t("console.platform.summary_description") }}</p></div><button type="button" :disabled="busy || !selectedConnectionId" @click="loadPlatformDashboard">{{ busy ? t("console.members.loading") : t("console.platform.load_summary") }}</button></div>
        <dl v-if="dashboardSummary" class="dashboard-metrics"><div><dt>{{ t("console.platform.messages_today") }}</dt><dd>{{ dashboardSummary.messages_today }}</dd></div><div><dt>{{ t("console.platform.ai_flagged_today") }}</dt><dd>{{ dashboardSummary.ai_flagged_today }}</dd></div><div><dt>{{ t("console.platform.creator_sources") }}</dt><dd>{{ dashboardSummary.creator_sources }}</dd></div><div><dt>{{ t("console.platform.bot_latency") }}</dt><dd>{{ dashboardSummary.bot_latency_ms === null ? t("console.platform.unavailable") : `${dashboardSummary.bot_latency_ms} ms` }}</dd></div></dl>
        <div class="section-heading"><div><h4>{{ t("console.platform.channels") }}</h4><p>{{ t("console.platform.channels_description") }}</p></div><button type="button" :disabled="busy || !selectedConnectionId" @click="loadPlatformChannels">{{ busy ? t("console.members.loading") : t("console.platform.load_channels") }}</button></div>
        <ul v-if="channelCatalog?.items.length" class="health-signals"><li v-for="channel in channelCatalog.items" :key="channel.id"><span><strong>{{ channel.name }}</strong><small>{{ channelKindLabel(channel.kind) }}</small></span></li></ul>
        <div class="section-heading"><div><h4>{{ t("console.platform.settings") }}</h4><p>{{ t("console.platform.settings_description") }}</p></div><button type="button" :disabled="busy || !selectedConnectionId" @click="loadPlatformBotSettings">{{ busy ? t("console.members.loading") : t("console.platform.load_settings") }}</button></div>
        <dl v-if="botSettings" class="dashboard-metrics"><div><dt>{{ t("console.platform.subscription") }}</dt><dd>{{ botSettings.subscription_tier }}</dd></div><div><dt>{{ t("console.platform.activity_rotation") }}</dt><dd>{{ botSettings.activity_rotation_enabled ? t("console.platform.enabled") : t("console.platform.disabled") }}</dd></div><div><dt>{{ t("console.platform.rotation_interval") }}</dt><dd>{{ formatSeconds(botSettings.activity_rotation_interval_seconds) }}</dd></div><div><dt>{{ t("console.platform.retention_rules") }}</dt><dd>{{ Object.keys(botSettings.retention_days).length }}</dd></div></dl>
        <div class="section-heading"><div><h4>{{ t("console.platform.integrations") }}</h4><p>{{ t("console.platform.integrations_description") }}</p></div><button type="button" :disabled="busy || !selectedConnectionId" @click="loadPlatformIntegrations">{{ busy ? t("console.members.loading") : t("console.platform.load_integrations") }}</button></div>
        <dl v-if="integrations" class="dashboard-metrics"><div><dt>{{ t("console.platform.discord_bot") }}</dt><dd>{{ integrations.discord_bot_status }}</dd></div><div><dt>{{ t("console.platform.creator_platforms") }}</dt><dd>{{ integrations.creator_platforms_status }}</dd></div><div><dt>{{ t("console.platform.creator_poll") }}</dt><dd>{{ formatSeconds(integrations.creator_poll_interval_seconds) }}</dd></div><div><dt>{{ t("console.platform.muxivo_core") }}</dt><dd>{{ integrations.muxivo_core_status }}</dd></div><div><dt>{{ t("console.platform.database") }}</dt><dd>{{ integrations.database_status }}</dd></div></dl>
        <div class="section-heading"><div><h4>{{ t("console.platform.statistics") }}</h4><p>{{ t("console.platform.statistics_description") }}</p></div><button type="button" :disabled="busy || !selectedConnectionId" @click="loadPlatformServerStatistics">{{ busy ? t("console.members.loading") : t("console.platform.load_statistics") }}</button></div>
        <dl v-if="serverStatistics" class="dashboard-metrics"><div><dt>{{ t("console.platform.period") }}</dt><dd>{{ t("console.platform.days", { value: serverStatistics.period_days }) }}</dd></div><div><dt>{{ t("console.platform.messages") }}</dt><dd>{{ serverStatistics.total_messages }}</dd></div><div><dt>{{ t("console.platform.active_users") }}</dt><dd>{{ serverStatistics.active_users }}</dd></div><div><dt>{{ t("console.platform.active_channels") }}</dt><dd>{{ serverStatistics.active_channels }}</dd></div><div><dt>{{ t("console.platform.members") }}</dt><dd>{{ serverStatistics.current_member_count }}</dd></div><div><dt>{{ t("console.platform.voice_minutes") }}</dt><dd>{{ serverStatistics.total_voice_minutes }}</dd></div><div><dt>{{ t("console.platform.net_member_growth") }}</dt><dd>{{ serverStatistics.net_member_growth }}</dd></div><div><dt>{{ t("console.platform.moderation_events") }}</dt><dd>{{ serverStatistics.moderation_events }}</dd></div></dl>
        <div class="section-heading"><div><h4>{{ t("console.platform.timeline") }}</h4><p>{{ t("console.platform.timeline_description") }}</p></div><button type="button" :disabled="busy || !selectedConnectionId" @click="loadPlatformAuditTimeline">{{ busy ? t("console.members.loading") : t("console.platform.load_timeline") }}</button></div>
        <ul v-if="auditTimeline?.items.length" class="health-signals"><li v-for="event in auditTimeline.items" :key="`${event.event_type}-${event.occurred_at}`"><span><strong>{{ event.event_type }}</strong><small>{{ new Date(event.occurred_at).toLocaleString() }}</small></span></li></ul>
        <p v-else-if="auditTimeline">{{ t("console.platform.no_timeline") }}</p>
      </section>
      <section v-if="selectedConnection" class="platform-health" aria-labelledby="platform-health-heading">
        <div class="section-heading"><div><h3 id="platform-health-heading">{{ t("console.platform.health_title", { platform: platformLabel(selectedConnection.platform) }) }}</h3><p>{{ t("console.platform.health_description") }}</p></div><button type="button" :disabled="busy" @click="loadPlatformHealth">{{ busy ? t("console.members.loading") : t("console.platform.load_health") }}</button></div>
        <ul v-if="platformHealth" class="health-signals"><li v-for="signal in platformHealth.signals" :key="signal.key"><span><strong>{{ signal.display_name }}</strong><small>{{ signal.value }}</small></span><em :data-status="signal.status">{{ signalStatusLabel(signal.status) }}</em></li></ul>
      </section>
      <section id="console-audit" v-if="activeOrganizationId" class="platform-dashboard console-section" aria-labelledby="organization-audit-heading">
        <div class="section-heading"><div><h3 id="organization-audit-heading">{{ t("console.audit.title") }}</h3><p>{{ t("console.audit.description") }}</p></div><button type="button" :disabled="busy" @click="loadOrganizationAuditEvents()">{{ busy ? t("console.members.loading") : t("console.audit.load") }}</button></div>
        <ul v-if="auditEvents.length" class="health-signals audit-events"><li v-for="event in auditEvents" :key="event.id"><span><strong>{{ event.action }}</strong><small>{{ new Date(event.created_at).toLocaleString() }} · {{ event.resource_type }}{{ event.resource_id ? ` · ${event.resource_id}` : "" }}</small></span><em :data-status="event.result">{{ event.result }}</em></li></ul>
        <p v-else-if="!busy">{{ t("console.audit.empty") }}</p>
        <button v-if="auditEventsNextCursor" class="load-more" type="button" :disabled="busy" @click="loadOrganizationAuditEvents(true)">{{ t("console.audit.older") }}</button>
      </section>
      <section id="console-discord" v-if="usableDiscordConnections.length" class="platform-dashboard console-section" aria-labelledby="discord-dashboard-heading">
        <div class="section-heading"><div><h3 id="discord-dashboard-heading">{{ t("console.discord.summary_title") }}</h3><p>{{ t("console.discord.summary_description") }}</p></div><button type="button" :disabled="busy || !selectedDiscordConnectionId" @click="loadDiscordDashboard">{{ busy ? t("console.members.loading") : t("console.platform.load_summary") }}</button></div>
        <label class="connection-picker">{{ t("console.discord.connection") }}<select v-model="selectedDiscordConnectionId" @change="selectDiscordConnection"><option v-for="connection in usableDiscordConnections" :key="connection.id" :value="connection.id">{{ connection.external_resource_id }} · {{ connectionStatusLabel(connection.status) }}</option></select></label>
        <dl v-if="dashboardSummary" class="dashboard-metrics"><div><dt>{{ t("console.platform.messages_today") }}</dt><dd>{{ dashboardSummary.messages_today }}</dd></div><div><dt>{{ t("console.platform.ai_flagged_today") }}</dt><dd>{{ dashboardSummary.ai_flagged_today }}</dd></div><div><dt>{{ t("console.platform.creator_sources") }}</dt><dd>{{ dashboardSummary.creator_sources }}</dd></div><div><dt>{{ t("console.platform.bot_latency") }}</dt><dd>{{ formatLatency(dashboardSummary.bot_latency_ms) }}</dd></div></dl>
      </section>
      <section v-if="usableDiscordConnections.length" class="platform-dashboard" aria-labelledby="discord-channels-heading">
        <div class="section-heading"><div><h3 id="discord-channels-heading">{{ t("console.discord.channels_title") }}</h3><p>{{ t("console.discord.channels_description") }}</p></div><button type="button" :disabled="busy || !selectedDiscordConnectionId" @click="loadDiscordChannels">{{ busy ? t("console.members.loading") : t("console.platform.load_channels") }}</button></div>
        <ul v-if="channelCatalog?.items.length" class="health-signals"><li v-for="channel in channelCatalog.items" :key="channel.id"><span><strong>{{ channel.name }}</strong><small>{{ channelKindLabel(channel.kind) }}</small></span></li></ul>
        <p v-else-if="channelCatalog && !channelCatalog.items.length">{{ t("console.discord.no_channels") }}</p>
      </section>
      <section v-if="usableDiscordConnections.length" class="platform-dashboard" aria-labelledby="discord-channel-purposes-heading">
        <div class="section-heading"><div><h3 id="discord-channel-purposes-heading">{{ t("console.discord.purposes_title") }}</h3><p>{{ t("console.discord.purposes_description") }}</p></div><button type="button" :disabled="busy || !selectedDiscordConnectionId" @click="loadDiscordChannelPurposes">{{ busy ? t("console.members.loading") : t("console.discord.load_assignments") }}</button></div>
        <ul v-if="channelPurposes?.items.length" class="health-signals"><li v-for="assignment in channelPurposes.items" :key="assignment.purpose"><span><strong>{{ purposeLabel(assignment.purpose) }}</strong><small>{{ assignment.channel_id }}</small></span></li></ul>
        <form v-if="channelCatalog?.items.length" @submit.prevent="saveDiscordChannelPurpose"><label>{{ t("console.discord.purpose") }}<select v-model="selectedPurpose"><option value="welcome">{{ t("console.purpose.welcome") }}</option><option value="member_log">{{ t("console.purpose.member_log") }}</option><option value="mod_log">{{ t("console.purpose.mod_log") }}</option><option value="message_log">{{ t("console.purpose.message_log") }}</option><option value="channel_log">{{ t("console.purpose.channel_log") }}</option><option value="stream_announce">{{ t("console.purpose.stream_announce") }}</option><option value="dev_blog">{{ t("console.purpose.dev_blog") }}</option><option value="ai_moderation_log">{{ t("console.purpose.ai_moderation_log") }}</option></select></label><label>{{ t("console.discord.text_channel") }}<select v-model="selectedPurposeChannelId" required><option disabled value="">{{ t("console.discord.select_channel") }}</option><option v-for="channel in channelCatalog.items.filter((item) => item.kind === 'text')" :key="channel.id" :value="channel.id">{{ channel.name }}</option></select></label><button :disabled="busy || !canRunSelectedDiscordWrites">{{ busy ? t("console.members.loading") : t("console.discord.save_assignment") }}</button></form>
      </section>
      <section v-if="usableDiscordConnections.length" class="platform-dashboard" aria-labelledby="discord-ai-moderation-heading">
        <div class="section-heading"><div><h3 id="discord-ai-moderation-heading">{{ t("console.discord.ai_title") }}</h3><p>{{ t("console.discord.ai_description") }}</p></div><button type="button" :disabled="busy || !selectedDiscordConnectionId" @click="loadDiscordAiModerationSummary">{{ busy ? t("console.members.loading") : t("console.discord.load_policy_summary") }}</button></div>
        <dl v-if="aiModerationSummary" class="dashboard-metrics"><div><dt>{{ t("console.discord.enforcement_mode") }}</dt><dd>{{ aiModerationSummary.enforcement_mode }}</dd></div><div><dt>{{ t("console.discord.test_mode") }}</dt><dd>{{ aiModerationSummary.test_mode ? t("console.platform.enabled") : t("console.platform.disabled") }}</dd></div><div><dt>{{ t("console.discord.covered_channels") }}</dt><dd>{{ aiModerationSummary.covered_channel_count }}</dd></div><div><dt>{{ t("console.discord.labels") }}</dt><dd>{{ aiModerationSummary.label_count }}</dd></div><div><dt>{{ t("console.discord.log_channel") }}</dt><dd>{{ aiModerationSummary.log_channel_configured ? t("console.discord.configured") : t("console.discord.not_configured") }}</dd></div><div><dt>{{ t("console.discord.automatic_actions") }}</dt><dd>{{ aiModerationSummary.automated_timeout_enabled || aiModerationSummary.automated_kick_enabled || aiModerationSummary.automated_ban_enabled ? t("console.platform.enabled") : t("console.platform.disabled") }}</dd></div></dl>
        <div class="section-heading policy-heading"><div><h4>{{ t("console.discord.policy_editor") }}</h4><p>{{ t("console.discord.policy_description") }}</p></div><button type="button" :disabled="busy || !selectedDiscordConnectionId || !canRunSelectedDiscordWrites" @click="loadDiscordAiModerationPolicy">{{ busy ? t("console.members.loading") : t("console.discord.load_editable_policy") }}</button></div>
        <form v-if="aiModerationPolicy" class="welcome-settings policy-settings" @submit.prevent="saveDiscordAiModerationPolicy">
          <p v-if="aiModerationPolicy.is_default_policy">{{ t("console.discord.default_policy") }}</p>
          <label>{{ t("console.discord.enforcement_mode") }}<select v-model="aiModerationPolicy.policy.enforcement_mode"><option value="SHADOW">{{ t("console.discord.shadow_option") }}</option><option value="LIMITED">{{ t("console.discord.limited_option") }}</option><option value="ELEVATED">{{ t("console.discord.elevated_option") }}</option></select></label>
          <label><input v-model="aiModerationPolicy.policy.test_mode" type="checkbox" /> {{ t("console.discord.test_mode") }}</label>
          <label>{{ t("console.discord.limited_confidence") }}<input v-model.number="aiModerationPolicy.policy.limited_min_confidence" type="number" min="0" max="1" step="0.01" required /></label>
          <label>{{ t("console.discord.blacklist_words") }}<textarea v-model="aiModerationBlacklistWords" maxlength="50000" :placeholder="t('console.discord.one_per_line')"></textarea></label>
          <label>{{ t("console.discord.allowed_domains") }}<textarea v-model="aiModerationAllowedDomains" maxlength="50000" :placeholder="t('console.discord.one_domain_per_line')"></textarea></label>
          <label><input v-model="aiModerationPolicy.policy.ocr_enabled" type="checkbox" /> {{ t("console.discord.ocr") }}</label>
          <label>{{ t("console.discord.ocr_failure_mode") }}<select v-model="aiModerationPolicy.policy.ocr_failure_mode"><option value="SKIP">{{ t("console.discord.skip_image") }}</option><option value="REVIEW">{{ t("console.discord.send_review") }}</option></select></label>
          <fieldset><legend>{{ t("console.discord.automatic_actions") }}</legend><label><input v-model="aiModerationPolicy.policy.allow_automated_timeout" type="checkbox" /> {{ t("console.discord.allow_timeouts") }}</label><label><input v-model="aiModerationPolicy.policy.allow_automated_kick" type="checkbox" /> {{ t("console.discord.allow_kicks") }}</label><label><input v-model="aiModerationPolicy.policy.allow_automated_ban" type="checkbox" /> {{ t("console.discord.allow_bans") }}</label><label><input v-model="aiModerationPolicy.policy.beta_enforcement_acknowledged" type="checkbox" /> {{ t("console.discord.acknowledge_risk") }}</label></fieldset>
          <p>{{ t("console.discord.policy_save_help") }}</p>
          <button :disabled="busy || !canRunSelectedDiscordWrites">{{ busy ? t("console.members.loading") : t("console.discord.save_policy") }}</button>
        </form>
      </section>
      <section v-if="usableDiscordConnections.length" class="platform-dashboard" aria-labelledby="discord-welcome-heading">
        <div class="section-heading"><div><h3 id="discord-welcome-heading">{{ t("console.discord.welcome_title") }}</h3><p>{{ t("console.discord.welcome_description") }}</p></div><button type="button" :disabled="busy || !selectedDiscordConnectionId" @click="loadDiscordWelcomeSettings">{{ busy ? t("console.members.loading") : t("console.discord.load_welcome") }}</button></div>
        <form v-if="welcomeSettings" class="welcome-settings" @submit.prevent="saveDiscordWelcomeSettings"><label><input v-model="welcomeSettings.is_enabled" type="checkbox" /> {{ t("console.discord.welcome_enabled") }}</label><label>{{ t("console.discord.title_label") }}<input v-model="welcomeSettings.title" maxlength="256" required /></label><label>{{ t("console.discord.description_label") }}<textarea v-model="welcomeSettings.description" maxlength="4096" required></textarea></label><label>{{ t("console.discord.color") }}<input v-model.number="welcomeSettings.color" type="number" min="0" max="16777215" required /></label><label>{{ t("console.discord.rules_channel") }}<input v-model="welcomeSettings.rules_channel_id" inputmode="numeric" /></label><label>{{ t("console.discord.roles_channel") }}<input v-model="welcomeSettings.roles_channel_id" inputmode="numeric" /></label><p>{{ t("console.discord.active_connection_help") }}</p><button :disabled="busy || !canRunSelectedDiscordWrites">{{ busy ? t("console.members.loading") : t("console.discord.save_welcome") }}</button></form>
       </section>
      </section>
        </main>
      </div>
    </section>
    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
  </div>
</template>
