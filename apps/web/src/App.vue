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
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { consoleApi, ConsoleApiError } from "./api/consoleApi";
import LanguageSwitcher from "./components/common/LanguageSwitcher.vue";
import PublicFooter from "./components/common/PublicFooter.vue";
import AuthModal from "./features/auth/AuthModal.vue";
import { useConsoleAuth } from "./features/auth/useConsoleAuth";
import ConnectionWizardPanel from "./features/console/ConnectionWizardPanel.vue";
import OrganizationMembersPanel from "./features/console/OrganizationMembersPanel.vue";
import OrganizationSwitcher from "./features/console/OrganizationSwitcher.vue";
import SecurityPanel from "./features/console/SecurityPanel.vue";
import { useOrganizationSelection } from "./features/console/useOrganizationSelection";
import { useI18n } from "./i18n";
import { clientLogger } from "./utils/clientLogger";
import { consoleErrorMessage } from "./utils/consoleError";
import {
  DEFAULT_MEMBER_SCOPE_OPTIONS,
  canManageOrganizationMembers as canManageOrganizationMembersForRole,
  memberRoleOptionsForActor,
  membershipAllows,
  supportedScopesForRole,
} from "./features/console/access";
import {
  nextConsoleTheme,
  persistConsoleTheme,
  readConsoleTheme,
} from "./utils/theme";
import {
  connectionWizardOptions,
  type ConnectablePlatform,
} from "./utils/connectionWizard";
import GetToKnowUs from "./views/GetToKnowUs.vue";
import MuxivoLanding from "./views/MuxivoLanding.vue";
import type {
  AiModerationAction,
  AiModerationLabelRule,
  AiModerationPolicy,
  AuditEvent,
  AuditEventPage,
  ConsoleSection,
  ControlModule,
  MembershipScopeInput,
  OrganizationInvitation,
  OrganizationMembership,
  OrganizationRole,
  PlatformAiModerationPolicyState,
  PlatformAiModerationSummary,
  PlatformAuditTimeline,
  PlatformBotSettings,
  PlatformChannel,
  PlatformChannelCatalog,
  PlatformChannelPurposes,
  PlatformConnection,
  PlatformConnectionGrantedScope,
  PlatformConnectionCandidate,
  PlatformConnectionCandidateCatalog,
  PlatformDashboardSummary,
  PlatformHealth,
  PlatformHealthSignal,
  PlatformIntegrations,
  PlatformServerStatistics,
  PlatformWelcomeSettings,
  Theme,
} from "./features/console/types";

const { t } = useI18n();

function messageFor(error: unknown): string {
  return consoleErrorMessage(error, t);
}

const initialTheme: Theme = readConsoleTheme(
  typeof window !== "undefined" ? window.localStorage : null,
);
const authenticated = ref(false);
const landingTab = ref<"overview" | "about">("overview");
const loginOpen = ref(false);
const loginVisible = ref(false);
let loginCloseTimer: ReturnType<typeof setTimeout> | null = null;
const loginTrigger = ref<HTMLButtonElement | null>(null);
const theme = ref<Theme>(initialTheme);
const activeConsoleSection = ref<ConsoleSection>("overview");
const busy = ref(false);
const notice = ref("");
const organizationInvitations = ref<OrganizationInvitation[]>([]);
const organizationMembers = ref<OrganizationMembership[]>([]);
const newMemberEmail = ref("");
const newMemberRole = ref<OrganizationRole>("viewer");
const newMemberScopes = ref<MembershipScopeInput[]>([
  { resource: "console.control_modules", action: "read" },
]);
const platform = ref<ConnectablePlatform>("discord");
const connectionCandidates = ref<PlatformConnectionCandidate[]>([]);
const connectionCandidatesIdentityLinked = ref<boolean | null>(null);
const connectionCandidatesLoading = ref(false);
const connectionCandidatesUnavailable = ref(false);
const selectedConnectionCandidateId = ref("");
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
    candidateLabel: t(`console.connections.wizard.${option.platform}.candidate`),
    candidateHelp: t(`console.connections.wizard.${option.platform}.candidate_help`),
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

function navLetters(label: string): string[] {
  return Array.from(label);
}

async function openLoginModal(): Promise<void> {
  if (loginCloseTimer !== null) {
    clearTimeout(loginCloseTimer);
    loginCloseTimer = null;
  }
  loginOpen.value = true;
  await nextTick();
  const enter = () => {
    loginVisible.value = true;
    clientLogger.info("console.auth.modal_entered");
  };
  if (typeof window !== "undefined") {
    window.requestAnimationFrame(enter);
  } else {
    enter();
  }
  clientLogger.info("console.auth.modal_open_requested");
}

function closeLoginModal(): void {
  if (!loginOpen.value) return;
  loginVisible.value = false;
  if (loginCloseTimer !== null) clearTimeout(loginCloseTimer);
  loginCloseTimer = setTimeout(() => {
    loginOpen.value = false;
    loginCloseTimer = null;
    loginTrigger.value?.focus();
    clientLogger.info("console.auth.modal_closed");
  }, 280);
  clientLogger.info("console.auth.modal_exit_started");
}

onBeforeUnmount(() => {
  if (loginCloseTimer !== null) clearTimeout(loginCloseTimer);
});

const {
  organizationName,
  organizations,
  organizationsLoaded,
  selectedOrganizationId,
  activeOrganization,
  activeOrganizationId,
  loadOrganizations,
  selectOrganization,
  createOrganization,
  resetOrganizationSelection,
} = useOrganizationSelection({
  t,
  busy,
  notice,
  messageFor,
  refreshOrganizationWorkspace,
  resetOrganizationWorkspace,
});

const {
  authMode,
  email,
  password,
  registrationDisplayName,
  registrationEmail,
  registrationPassword,
  currentPassword,
  reauthenticationPassword,
  newPassword,
  confirmNewPassword,
  recoveryEmail,
  recoveryToken,
  recoveryNewPassword,
  recoveryConfirmPassword,
  registrationCode,
  registrationVerificationSent,
  registrationEmailVerified,
  invitationToken,
  identityLinkedProvider,
  availableAuthProviders,
  browserSessions,
  loginIdentities,
  signIn,
  requestRegistrationVerification,
  resendRegistrationVerification,
  verifyRegistration,
  resetRegistrationVerification,
  continueToSignIn,
  loadAuthProviders,
  signInWithProvider,
  requestPasswordRecovery,
  completePasswordRecovery,
  linkExternalIdentity,
  loadBrowserSessions,
  refreshSecurity,
  loadLoginIdentities,
  unlinkLoginIdentity,
  changePassword,
  refreshRecentAuthentication,
  clearInvitationToken,
  providerLabel,
} = useConsoleAuth({
  t,
  busy,
  notice,
  authenticated,
  messageFor,
  closeLoginModal,
  loadOrganizations,
  acceptInvitationIfPresent,
});

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
const canManageOrganizationMembers = computed(
  () => canManageOrganizationMembersForRole(activeOrganization.value?.membership.role),
);
const canReadPlatformConnections = computed(() =>
  membershipAllows(
    activeOrganization.value?.membership,
    "console.platform_connections",
    "read",
  ),
);
const canManagePlatformConnections = computed(() =>
  membershipAllows(
    activeOrganization.value?.membership,
    "console.platform_connections",
    "manage",
  ),
);
const selectableConnectionCandidates = computed(() =>
  connectionCandidates.value.filter(
    (candidate) =>
      !connections.value.some(
        (connection) =>
          connection.platform === candidate.platform &&
          connection.external_resource_id === candidate.external_resource_id,
      ),
  ),
);
const selectedConnectionCandidate = computed(
  () =>
    selectableConnectionCandidates.value.find(
      (candidate) => candidate.external_resource_id === selectedConnectionCandidateId.value,
    ) ?? null,
);
const currentBrowserSession = computed(
  () => browserSessions.value.find((session) => session.is_current) ?? null,
);
const canRevokeAllBrowserSessions = computed(
  () => currentBrowserSession.value?.assurance_level === "recent_authentication",
);
const availableMemberRoleOptions = computed<OrganizationRole[]>(() =>
  memberRoleOptionsForActor(activeOrganization.value?.membership.role),
);
const memberScopeOptions: MembershipScopeInput[] = DEFAULT_MEMBER_SCOPE_OPTIONS.map((scope) => ({
  ...scope,
}));
const availableNewMemberScopeOptions = computed(() =>
  supportedScopesForRole(newMemberRole.value, memberScopeOptions),
);

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
    organizationInvitations.value = [];
    organizationMembers.value = [];
    clearInvitationToken();
    resetOrganizationWorkspace();
    resetOrganizationSelection();
    notice.value = t("console.notice.signed_out");
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

onMounted(async () => {
  if (invitationToken.value || recoveryToken.value) void openLoginModal();
  const linkedProvider = identityLinkedProvider.value;
  if (linkedProvider && typeof window !== "undefined") {
    const url = new URL(window.location.href);
    url.searchParams.delete("identity_linked");
    window.history.replaceState({}, "", url);
  }
  await loadAuthProviders();
  try {
    await consoleApi<{ authenticated: boolean }>("/api/v1/auth/session");
    authenticated.value = true;
    await Promise.all([loadOrganizations(), loadBrowserSessions(), loadLoginIdentities()]);
    await acceptInvitationIfPresent();
  } catch {
    // A missing session is the normal first-visit state.
  }
  if (linkedProvider) {
    notice.value = t("console.notice.identity_linked", {
      platform: providerLabel(linkedProvider),
    });
    activeConsoleSection.value = "connections";
  }
});

async function linkDiscord() {
  await linkExternalIdentity("discord");
}

async function linkTwitch() {
  await linkExternalIdentity("twitch");
}

async function linkTelegram() {
  await linkExternalIdentity("telegram");
}

async function linkGoogle() {
  await linkExternalIdentity("google");
}

async function linkYandex() {
  await linkExternalIdentity("yandex");
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
    organizationInvitations.value = [];
    clearInvitationToken();
    resetOrganizationWorkspace();
    resetOrganizationSelection();
    notice.value = t("console.notice.sessions_revoked", { count: payload.revoked_count });
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function refreshOrganizationWorkspace() {
  resetOrganizationWorkspace();
  if (!activeOrganizationId.value) return;
  await Promise.all([
    loadConnections(),
    loadConnectionCandidates(),
    loadOrganizationMembers(),
    loadOrganizationInvitations(),
  ]);
}

function resetOrganizationWorkspace() {
  connections.value = [];
  connectionCandidates.value = [];
  connectionCandidatesIdentityLinked.value = null;
  connectionCandidatesLoading.value = false;
  connectionCandidatesUnavailable.value = false;
  selectedConnectionCandidateId.value = "";
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

async function loadConnections() {
  if (!activeOrganizationId.value || !canReadPlatformConnections.value) {
    connections.value = [];
    return;
  }
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
    syncSelectedConnectionCandidate();
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadConnectionCandidates() {
  if (!activeOrganizationId.value || !canManagePlatformConnections.value) {
    connectionCandidates.value = [];
    connectionCandidatesIdentityLinked.value = null;
    connectionCandidatesLoading.value = false;
    connectionCandidatesUnavailable.value = false;
    selectedConnectionCandidateId.value = "";
    return;
  }
  const requestedPlatform = platform.value;
  const requestedOrganizationId = activeOrganizationId.value;
  connectionCandidatesLoading.value = true;
  connectionCandidatesUnavailable.value = false;
  try {
    const payload = await consoleApi<PlatformConnectionCandidateCatalog>(
      `/api/v1/organizations/${encodeURIComponent(requestedOrganizationId)}/platform-connection-candidates?platform=${encodeURIComponent(requestedPlatform)}`,
    );
    if (
      requestedPlatform !== platform.value ||
      requestedOrganizationId !== activeOrganizationId.value
    ) {
      return;
    }
    connectionCandidates.value = payload.items;
    connectionCandidatesIdentityLinked.value = payload.identity_linked;
    syncSelectedConnectionCandidate();
  } catch (error) {
    if (
      requestedPlatform !== platform.value ||
      requestedOrganizationId !== activeOrganizationId.value
    ) {
      return;
    }
    connectionCandidates.value = [];
    connectionCandidatesIdentityLinked.value = null;
    connectionCandidatesUnavailable.value = error instanceof ConsoleApiError && error.status === 503;
    if (!(error instanceof ConsoleApiError && error.status === 503)) {
      notice.value = messageFor(error);
    }
  } finally {
    if (
      requestedPlatform === platform.value &&
      requestedOrganizationId === activeOrganizationId.value
    ) {
      connectionCandidatesLoading.value = false;
    }
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

function normalizeNewMemberScopes() {
  newMemberScopes.value = supportedScopesForRole(
    newMemberRole.value,
    newMemberScopes.value,
  );
}

function normalizeMemberScopes(member: OrganizationMembership) {
  member.resource_scopes = supportedScopesForRole(member.role, member.resource_scopes);
}

function roleLabel(role: OrganizationRole): string {
  return t(`console.roles.${role}`);
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

function connectionStatusDescription(connection: PlatformConnection): string {
  const descriptions: Record<PlatformConnection["status"], string> = {
    pending: t("console.connection_status_description.pending"),
    active: t("console.connection_status_description.active"),
    degraded: t("console.connection_status_description.degraded"),
    reauth_required: t("console.connection_status_description.reauth_required"),
    disconnected: t("console.connection_status_description.disconnected"),
  };
  const statusDescription = descriptions[connection.status];
  if (!connection.status_reason) return statusDescription;
  const reasonDescription = t(`console.connection_reason.${connection.status_reason}`);
  return `${statusDescription} ${t("console.connection_reason_prefix", { reason: reasonDescription })}`;
}

function connectionRiskyActionsBlocked(status: PlatformConnection["status"]): boolean {
  return ["degraded", "reauth_required", "disconnected"].includes(status);
}

function syncSelectedConnectionCandidate() {
  if (
    selectedConnectionCandidateId.value &&
    selectableConnectionCandidates.value.some(
      (candidate) =>
        candidate.external_resource_id === selectedConnectionCandidateId.value,
    )
  ) {
    return;
  }
  selectedConnectionCandidateId.value =
    selectableConnectionCandidates.value[0]?.external_resource_id ?? "";
}

function selectConnectionWizard(nextPlatform: ConnectablePlatform) {
  platform.value = nextPlatform;
  connectionCandidates.value = [];
  connectionCandidatesIdentityLinked.value = null;
  connectionCandidatesUnavailable.value = false;
  selectedConnectionCandidateId.value = "";
  void loadConnectionCandidates();
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
  if (!activeOrganizationId.value || !selectedConnectionCandidate.value) {
    notice.value = t("console.connections.select_candidate_required");
    return;
  }
  busy.value = true;
  notice.value = "";
  try {
    const connection = await consoleApi<PlatformConnection>(
      `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections`,
      {
        method: "POST",
        body: JSON.stringify({
          platform: platform.value,
          external_resource_id: selectedConnectionCandidate.value.external_resource_id,
        }),
      },
    );
    selectedConnectionCandidateId.value = "";
    connections.value = [connection, ...connections.value];
    syncSelectedConnectionCandidate();
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
          <button ref="loginTrigger" class="panel-cta" type="button" @click="openLoginModal">
            {{ t("header.see_panel") }}
          </button>
        </div>
      </header>

      <MuxivoLanding v-if="landingTab === 'overview'" id="top" />
      <GetToKnowUs v-else id="top" />
      <PublicFooter />
      <AuthModal
        v-if="loginOpen"
        v-model:auth-mode="authMode"
        v-model:email="email"
        v-model:password="password"
        v-model:registration-display-name="registrationDisplayName"
        v-model:registration-email="registrationEmail"
        v-model:registration-password="registrationPassword"
        v-model:recovery-email="recoveryEmail"
        v-model:recovery-token="recoveryToken"
        v-model:recovery-new-password="recoveryNewPassword"
        v-model:recovery-confirm-password="recoveryConfirmPassword"
        v-model:registration-code="registrationCode"
        :visible="loginVisible"
        :busy="busy"
        :notice="notice"
        :invitation-token="invitationToken"
        :registration-verification-sent="registrationVerificationSent"
        :registration-email-verified="registrationEmailVerified"
        :available-providers="availableAuthProviders"
        @close="closeLoginModal"
        @sign-in="signIn"
        @request-recovery="requestPasswordRecovery"
        @complete-recovery="completePasswordRecovery"
        @request-registration-verification="requestRegistrationVerification"
        @resend-registration-verification="resendRegistrationVerification"
        @verify-registration="verifyRegistration"
        @reset-registration-verification="resetRegistrationVerification"
        @continue-sign-in="continueToSignIn"
        @oauth-provider="signInWithProvider"
      />
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

        <OrganizationSwitcher
          id="console-organization-select"
          v-model="selectedOrganizationId"
          :organizations="organizations"
          :disabled="busy"
          variant="sidebar"
          @change="selectOrganization"
        />

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
      <div v-if="!organizationsLoaded" class="identity-link" role="status">
        <h2>{{ t("console.overview.loading_title") }}</h2>
        <p>{{ t("console.overview.loading_description") }}</p>
      </div>
      <div v-else-if="!organizations.length" class="identity-link">
        <h2>{{ t("console.overview.create_title") }}</h2>
        <p>{{ t("console.overview.create_description") }}</p>
        <form @submit.prevent="createOrganization"><label>{{ t("console.overview.name") }}<input v-model="organizationName" maxlength="128" required /></label><button :disabled="busy">{{ busy ? t("console.overview.creating") : t("console.overview.create_button") }}</button></form>
      </div>
      <div v-else class="identity-link">
        <span class="eyebrow">{{ t("console.overview.active_eyebrow") }}</span>
        <h2>{{ activeOrganization?.organization.name }}</h2>
        <p>{{ t("console.overview.active_description", { slug: activeOrganization?.organization.slug ?? "" }) }}</p>
        <OrganizationSwitcher
          id="console-overview-organization-select"
          v-model="selectedOrganizationId"
          :organizations="organizations"
          :disabled="busy"
          @change="selectOrganization"
        />
        <button type="button" :disabled="busy" @click="scrollToConsoleSection('connections')">
          {{ t("console.overview.open_connections") }}
        </button>
      </div>
      <div class="identity-provider-grid">
        <div class="identity-link">
          <h3>{{ t("console.overview.discord_identity") }}</h3>
          <p>{{ t("console.overview.discord_description") }}</p>
          <button
            type="button"
            :disabled="busy || !availableAuthProviders.includes('discord')"
            @click="linkDiscord"
          >{{ t("console.overview.link_discord") }}</button>
        </div>
        <div class="identity-link">
          <h3>{{ t("console.overview.twitch_identity") }}</h3>
          <p>{{ t("console.overview.twitch_description") }}</p>
          <button
            type="button"
            :disabled="busy || !availableAuthProviders.includes('twitch')"
            @click="linkTwitch"
          >{{ t("console.overview.link_twitch") }}</button>
        </div>
        <div class="identity-link">
          <h3>{{ t("console.overview.telegram_identity") }}</h3>
          <p>{{ t("console.overview.telegram_description") }}</p>
          <button
            type="button"
            :disabled="busy || !availableAuthProviders.includes('telegram')"
            @click="linkTelegram"
          >{{ t("console.overview.link_telegram") }}</button>
        </div>
        <div class="identity-link">
          <h3>{{ t("console.overview.google_identity") }}</h3>
          <p>{{ t("console.overview.google_description") }}</p>
          <button
            type="button"
            :disabled="busy || !availableAuthProviders.includes('google')"
            @click="linkGoogle"
          >{{ t("console.overview.link_google") }}</button>
        </div>
        <div class="identity-link">
          <h3>{{ t("console.overview.yandex_identity") }}</h3>
          <p>{{ t("console.overview.yandex_description") }}</p>
          <button
            type="button"
            :disabled="busy || !availableAuthProviders.includes('yandex')"
            @click="linkYandex"
          >{{ t("console.overview.link_yandex") }}</button>
        </div>
      </div>
    </section>
    <SecurityPanel
      v-model:reauthentication-password="reauthenticationPassword"
      v-model:current-password="currentPassword"
      v-model:new-password="newPassword"
      v-model:confirm-new-password="confirmNewPassword"
      :busy="busy"
      :browser-sessions="browserSessions"
      :login-identities="loginIdentities"
      :can-revoke-all-browser-sessions="canRevokeAllBrowserSessions"
      @refresh-security="refreshSecurity"
      @refresh-recent-authentication="refreshRecentAuthentication"
      @refresh-identities="loadLoginIdentities"
      @unlink-identity="unlinkLoginIdentity"
      @change-password="changePassword"
      @revoke-current-session="revokeCurrentSession"
      @revoke-all-sessions="revokeAllSessions"
    />
    <section id="console-connections" class="card workspace console-section">
      <h2>{{ t("console.connections.title") }}</h2>
      <p>{{ t("console.connections.description") }}</p>
      <div v-if="organizations.length" class="identity-link">
        <h3>{{ t("console.connections.active_org_title") }}</h3>
        <OrganizationSwitcher
          id="console-connections-organization-select"
          v-model="selectedOrganizationId"
          :organizations="organizations"
          :disabled="busy"
          :label="t('console.connections.organization_label')"
          :show-active-organization="false"
          @change="selectOrganization"
        />
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
      <ConnectionWizardPanel
        v-if="activeOrganizationId && canManagePlatformConnections"
        v-model:selected-connection-candidate-id="selectedConnectionCandidateId"
        :busy="busy"
        :platform="platform"
        :localized-connection-wizard-options="localizedConnectionWizardOptions"
        :selected-connection-wizard="selectedConnectionWizard"
        :connection-candidates-loading="connectionCandidatesLoading"
        :connection-candidates-unavailable="connectionCandidatesUnavailable"
        :connection-candidates-identity-linked="connectionCandidatesIdentityLinked"
        :selectable-connection-candidates="selectableConnectionCandidates"
        @select-platform="selectConnectionWizard"
        @register="registerConnection"
        @load-candidates="loadConnectionCandidates"
        @link-identity="linkExternalIdentity"
      />
      <p v-else-if="activeOrganizationId" class="connection-feedback" role="status">
        {{ t("console.connections.permission_required") }}
      </p>
      <ul v-if="connections.length" class="connections">
        <li v-for="connection in connections" :key="connection.id">
          <strong>{{ platformLabel(connection.platform) }}</strong>
          <span>
            {{ connection.external_resource_id }}
            <small>{{ connectionStatusDescription(connection) }}</small>
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
      <OrganizationMembersPanel
        v-if="canManageOrganizationMembers"
        v-model:new-member-email="newMemberEmail"
        v-model:new-member-role="newMemberRole"
        v-model:new-member-scopes="newMemberScopes"
        :actor-role="activeOrganization?.membership.role"
        :busy="busy"
        :organization-members="organizationMembers"
        :organization-invitations="organizationInvitations"
        :available-member-role-options="availableMemberRoleOptions"
        :available-new-member-scope-options="availableNewMemberScopeOptions"
        @load-members="loadOrganizationMembers"
        @invite-member="addOrganizationMember"
        @load-invitations="loadOrganizationInvitations"
        @revoke-invitation="revokeOrganizationInvitation"
        @save-member="saveOrganizationMember"
        @remove-member="removeOrganizationMember"
        @normalize-new-member-scopes="normalizeNewMemberScopes"
      />
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
