import { ref, type ComputedRef, type Ref } from "vue";

import { consoleApi } from "../../api/consoleApi";
import type { TranslationParams } from "../../i18n";
import { clientLogger } from "../../utils/clientLogger";
import type {
  AuditEvent,
  AuditEventPage,
  ControlModule,
  PlatformAiModerationPolicyState,
  PlatformAiModerationSummary,
  PlatformAuditTimeline,
  PlatformBotSettings,
  PlatformChannel,
  PlatformChannelCatalog,
  PlatformChannelPurposes,
  PlatformConnection,
  PlatformDashboardSummary,
  PlatformHealth,
  PlatformIntegrations,
  PlatformServerStatistics,
  PlatformWelcomeSettings,
} from "./types";

type Translate = (key: string, params?: TranslationParams) => string;
type LogContext = Record<string, string | number | boolean | undefined>;

type PlatformDashboardDependencies = {
  t: Translate;
  busy: Ref<boolean>;
  notice: Ref<string>;
  messageFor: (error: unknown) => string;
  activeOrganizationId: ComputedRef<string>;
  selectedConnectionId: Ref<string>;
  selectedDiscordConnectionId: Ref<string>;
  selectedConnection: ComputedRef<PlatformConnection | null>;
  canRunSelectedDiscordWrites: ComputedRef<boolean>;
  canReadOrganizationAuditEvents: ComputedRef<boolean>;
};

type RequestOptions<T> = {
  event: string;
  request: () => Promise<T>;
  onSuccess: (payload: T) => void;
  onFailure: () => void;
  successContext?: (payload: T) => LogContext;
};

/** Owns platform dashboard state and the API orchestration behind dashboard panels. */
export function usePlatformDashboard(dependencies: PlatformDashboardDependencies) {
  const {
    t,
    busy,
    notice,
    messageFor,
    activeOrganizationId,
    selectedConnectionId,
    selectedDiscordConnectionId,
    selectedConnection,
    canRunSelectedDiscordWrites,
    canReadOrganizationAuditEvents,
  } = dependencies;

  const platformHealth = ref<PlatformHealth | null>(null);
  const controlModules = ref<ControlModule[]>([]);
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

  async function runRequest<T>(options: RequestOptions<T>): Promise<boolean> {
    busy.value = true;
    notice.value = "";
    clientLogger.info(`${options.event}.requested`);
    try {
      const payload = await options.request();
      options.onSuccess(payload);
      clientLogger.info(`${options.event}.completed`, options.successContext?.(payload));
      return true;
    } catch (error) {
      options.onFailure();
      notice.value = messageFor(error);
      clientLogger.warn(`${options.event}.failed`, {
        error_type: error instanceof Error ? error.name : "unknown",
      });
      return false;
    } finally {
      busy.value = false;
    }
  }

  function organizationPath(): string | null {
    if (!activeOrganizationId.value) return null;
    return `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}`;
  }

  function selectedConnectionPath(): string | null {
    const organization = organizationPath();
    if (!organization || !selectedConnectionId.value) return null;
    return `${organization}/platform-connections/${encodeURIComponent(selectedConnectionId.value)}`;
  }

  function selectedDiscordConnectionPath(): string | null {
    const organization = organizationPath();
    if (!organization || !selectedDiscordConnectionId.value) return null;
    return `${organization}/platform-connections/${encodeURIComponent(selectedDiscordConnectionId.value)}`;
  }

  async function loadControlModules(): Promise<void> {
    const path = organizationPath();
    if (!path) {
      clientLogger.info("console.dashboard.modules.load_skipped", {
        has_active_organization: false,
      });
      return;
    }
    await runRequest({
      event: "console.dashboard.modules.load",
      request: () => consoleApi<{ items: ControlModule[] }>(`${path}/control-modules`),
      onSuccess: (payload) => {
        controlModules.value = payload.items;
      },
      onFailure: () => {
        controlModules.value = [];
      },
      successContext: (payload) => ({ count: payload.items.length }),
    });
  }

  async function loadPlatformDashboard(): Promise<void> {
    const path = selectedConnectionPath();
    if (!path) {
      clientLogger.info("console.dashboard.platform_summary.load_skipped", {
        has_active_organization: Boolean(activeOrganizationId.value),
        has_selected_connection: Boolean(selectedConnectionId.value),
      });
      return;
    }
    await runRequest({
      event: "console.dashboard.platform_summary.load",
      request: () => consoleApi<PlatformDashboardSummary>(`${path}/dashboard`),
      onSuccess: (payload) => {
        dashboardSummary.value = payload;
      },
      onFailure: () => {
        dashboardSummary.value = null;
      },
    });
  }

  async function loadPlatformChannels(): Promise<void> {
    const path = selectedConnectionPath();
    if (!path) return;
    await runRequest({
      event: "console.dashboard.platform_channels.load",
      request: () => consoleApi<PlatformChannelCatalog>(`${path}/channels`),
      onSuccess: (payload) => {
        channelCatalog.value = payload;
      },
      onFailure: () => {
        channelCatalog.value = null;
      },
      successContext: (payload) => ({ count: payload.items.length }),
    });
  }

  async function loadPlatformBotSettings(): Promise<void> {
    const path = selectedConnectionPath();
    if (!path) return;
    await runRequest({
      event: "console.dashboard.bot_settings.load",
      request: () => consoleApi<PlatformBotSettings>(`${path}/bot-settings`),
      onSuccess: (payload) => {
        botSettings.value = payload;
      },
      onFailure: () => {
        botSettings.value = null;
      },
    });
  }

  async function loadPlatformIntegrations(): Promise<void> {
    const path = selectedConnectionPath();
    if (!path) return;
    await runRequest({
      event: "console.dashboard.integrations.load",
      request: () => consoleApi<PlatformIntegrations>(`${path}/integrations`),
      onSuccess: (payload) => {
        integrations.value = payload;
      },
      onFailure: () => {
        integrations.value = null;
      },
    });
  }

  async function loadPlatformServerStatistics(): Promise<void> {
    const path = selectedConnectionPath();
    if (!path) return;
    await runRequest({
      event: "console.dashboard.server_statistics.load",
      request: () => consoleApi<PlatformServerStatistics>(`${path}/server-statistics`),
      onSuccess: (payload) => {
        serverStatistics.value = payload;
      },
      onFailure: () => {
        serverStatistics.value = null;
      },
    });
  }

  async function loadPlatformAuditTimeline(): Promise<void> {
    const path = selectedConnectionPath();
    if (!path) return;
    await runRequest({
      event: "console.dashboard.platform_audit_timeline.load",
      request: () => consoleApi<PlatformAuditTimeline>(`${path}/audit-timeline`),
      onSuccess: (payload) => {
        auditTimeline.value = payload;
      },
      onFailure: () => {
        auditTimeline.value = null;
      },
    });
  }

  function resetPlatformConnectionDetails(): void {
    dashboardSummary.value = null;
    channelCatalog.value = null;
    botSettings.value = null;
    integrations.value = null;
    platformHealth.value = null;
    clientLogger.info("console.dashboard.platform_connection.reset");
  }

  async function loadDiscordDashboard(): Promise<void> {
    const path = selectedDiscordConnectionPath();
    if (!path) return;
    await runRequest({
      event: "console.dashboard.discord_summary.load",
      request: () => consoleApi<PlatformDashboardSummary>(`${path}/dashboard`),
      onSuccess: (payload) => {
        dashboardSummary.value = payload;
      },
      onFailure: () => {
        dashboardSummary.value = null;
      },
    });
  }

  async function loadOrganizationAuditEvents(nextPage = false): Promise<void> {
    const path = organizationPath();
    if (
      !path ||
      !canReadOrganizationAuditEvents.value ||
      (nextPage && !auditEventsNextCursor.value)
    ) {
      if (!canReadOrganizationAuditEvents.value) {
        auditEvents.value = [];
        auditEventsNextCursor.value = null;
      }
      clientLogger.info("console.dashboard.audit.load_skipped", {
        has_active_organization: Boolean(activeOrganizationId.value),
        can_read_audit_events: canReadOrganizationAuditEvents.value,
        has_next_cursor: Boolean(auditEventsNextCursor.value),
      });
      return;
    }
    const query = nextPage ? `?after=${encodeURIComponent(auditEventsNextCursor.value ?? "")}` : "";
    await runRequest({
      event: "console.dashboard.audit.load",
      request: () => consoleApi<AuditEventPage>(`${path}/audit-events${query}`),
      onSuccess: (page) => {
        auditEvents.value = nextPage ? [...auditEvents.value, ...page.items] : page.items;
        auditEventsNextCursor.value = page.next_cursor;
      },
      onFailure: () => {
        if (!nextPage) {
          auditEvents.value = [];
          auditEventsNextCursor.value = null;
        }
      },
      successContext: (page) => ({
        count: page.items.length,
        next_page: Boolean(page.next_cursor),
      }),
    });
  }

  async function loadDiscordChannels(): Promise<void> {
    const path = selectedDiscordConnectionPath();
    if (!path) return;
    await runRequest({
      event: "console.dashboard.discord_channels.load",
      request: () => consoleApi<PlatformChannelCatalog>(`${path}/channels`),
      onSuccess: (payload) => {
        channelCatalog.value = payload;
      },
      onFailure: () => {
        channelCatalog.value = null;
      },
      successContext: (payload) => ({ count: payload.items.length }),
    });
  }

  async function loadDiscordChannelPurposes(): Promise<void> {
    const path = selectedDiscordConnectionPath();
    if (!path) return;
    await runRequest({
      event: "console.dashboard.discord_purposes.load",
      request: () => consoleApi<PlatformChannelPurposes>(`${path}/channel-purposes`),
      onSuccess: (payload) => {
        channelPurposes.value = payload;
      },
      onFailure: () => {
        channelPurposes.value = null;
      },
      successContext: (payload) => ({ count: payload.items.length }),
    });
  }

  async function loadDiscordAiModerationSummary(): Promise<void> {
    const path = selectedDiscordConnectionPath();
    if (!path) return;
    await runRequest({
      event: "console.dashboard.discord_ai_summary.load",
      request: () => consoleApi<PlatformAiModerationSummary>(`${path}/ai-moderation-summary`),
      onSuccess: (payload) => {
        aiModerationSummary.value = payload;
      },
      onFailure: () => {
        aiModerationSummary.value = null;
      },
    });
  }

  async function loadDiscordAiModerationPolicy(): Promise<void> {
    const path = selectedDiscordConnectionPath();
    if (!path || !canRunSelectedDiscordWrites.value) return;
    await runRequest({
      event: "console.dashboard.discord_ai_policy.load",
      request: () => consoleApi<PlatformAiModerationPolicyState>(`${path}/ai-moderation-policy`),
      onSuccess: (state) => {
        aiModerationPolicy.value = state;
        aiModerationBlacklistWords.value = state.policy.blacklist_words.join("\n");
        aiModerationAllowedDomains.value = state.policy.allowed_domains.join("\n");
      },
      onFailure: () => {
        aiModerationPolicy.value = null;
      },
    });
  }

  async function saveDiscordAiModerationPolicy(): Promise<void> {
    const path = selectedDiscordConnectionPath();
    if (!path || !aiModerationPolicy.value || !canRunSelectedDiscordWrites.value) return;
    const policy = {
      ...aiModerationPolicy.value.policy,
      blacklist_words: splitPolicyValues(aiModerationBlacklistWords.value),
      allowed_domains: splitPolicyValues(aiModerationAllowedDomains.value),
    };
    await runRequest({
      event: "console.dashboard.discord_ai_policy.save",
      request: () =>
        consoleApi<PlatformAiModerationSummary>(`${path}/ai-moderation-policy`, {
          method: "PUT",
          body: JSON.stringify(policy),
        }),
      onSuccess: (summary) => {
        aiModerationSummary.value = summary;
        aiModerationPolicy.value = {
          ...aiModerationPolicy.value!,
          policy,
          is_default_policy: false,
        };
        notice.value = t("console.notice.policy_saved");
      },
      onFailure: () => undefined,
    });
  }

  async function saveDiscordChannelPurpose(): Promise<void> {
    const path = selectedDiscordConnectionPath();
    if (!path || !selectedPurposeChannelId.value || !canRunSelectedDiscordWrites.value) return;
    await runRequest({
      event: "console.dashboard.discord_purpose.save",
      request: () =>
        consoleApi<PlatformChannelPurposes>(`${path}/channel-purposes`, {
          method: "PUT",
          body: JSON.stringify({
            purpose: selectedPurpose.value,
            channel_id: selectedPurposeChannelId.value,
          }),
        }),
      onSuccess: (payload) => {
        channelPurposes.value = payload;
        notice.value = t("console.notice.purpose_saved");
      },
      onFailure: () => undefined,
    });
  }

  async function loadDiscordWelcomeSettings(): Promise<void> {
    const path = selectedDiscordConnectionPath();
    if (!path) return;
    await runRequest({
      event: "console.dashboard.discord_welcome.load",
      request: () => consoleApi<PlatformWelcomeSettings>(`${path}/welcome-settings`),
      onSuccess: (payload) => {
        welcomeSettings.value = payload;
      },
      onFailure: () => {
        welcomeSettings.value = null;
      },
    });
  }

  async function saveDiscordWelcomeSettings(): Promise<void> {
    const path = selectedDiscordConnectionPath();
    if (!path || !welcomeSettings.value || !canRunSelectedDiscordWrites.value) return;
    const settings = welcomeSettings.value;
    await runRequest({
      event: "console.dashboard.discord_welcome.save",
      request: () =>
        consoleApi<PlatformWelcomeSettings>(`${path}/welcome-settings`, {
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
        }),
      onSuccess: (payload) => {
        welcomeSettings.value = payload;
        notice.value = t("console.notice.welcome_saved");
      },
      onFailure: () => undefined,
    });
  }

  function resetDiscordConnectionDetails(): void {
    dashboardSummary.value = null;
    channelCatalog.value = null;
    welcomeSettings.value = null;
    channelPurposes.value = null;
    aiModerationSummary.value = null;
    aiModerationPolicy.value = null;
    aiModerationBlacklistWords.value = "";
    aiModerationAllowedDomains.value = "";
    auditEvents.value = [];
    auditEventsNextCursor.value = null;
    clientLogger.info("console.dashboard.discord_connection.reset");
  }

  async function loadPlatformHealth(): Promise<void> {
    const organization = organizationPath();
    const connection = selectedConnection.value;
    if (!organization || !connection) return;
    await runRequest({
      event: "console.dashboard.platform_health.load",
      request: () =>
        consoleApi<PlatformHealth>(
          `${organization}/platforms/${encodeURIComponent(connection.platform)}/health`,
        ),
      onSuccess: (payload) => {
        platformHealth.value = payload;
      },
      onFailure: () => {
        platformHealth.value = null;
      },
      successContext: (payload) => ({ count: payload.signals.length }),
    });
  }

  function resetPlatformDashboard(): void {
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
    aiModerationBlacklistWords.value = "";
    aiModerationAllowedDomains.value = "";
    auditEvents.value = [];
    auditEventsNextCursor.value = null;
    selectedPurpose.value = "welcome";
    selectedPurposeChannelId.value = "";
    clientLogger.info("console.dashboard.workspace.reset");
  }

  function splitPolicyValues(value: string): string[] {
    return [...new Set(value.split(/[\n,]/).map((item) => item.trim()).filter(Boolean))];
  }

  return {
    platformHealth,
    controlModules,
    dashboardSummary,
    channelCatalog,
    botSettings,
    integrations,
    serverStatistics,
    auditTimeline,
    welcomeSettings,
    channelPurposes,
    aiModerationSummary,
    aiModerationPolicy,
    aiModerationBlacklistWords,
    aiModerationAllowedDomains,
    auditEvents,
    auditEventsNextCursor,
    selectedPurpose,
    selectedPurposeChannelId,
    loadControlModules,
    loadPlatformDashboard,
    loadPlatformChannels,
    loadPlatformBotSettings,
    loadPlatformIntegrations,
    loadPlatformServerStatistics,
    loadPlatformAuditTimeline,
    resetPlatformConnectionDetails,
    loadDiscordDashboard,
    loadOrganizationAuditEvents,
    loadDiscordChannels,
    loadDiscordChannelPurposes,
    loadDiscordAiModerationSummary,
    loadDiscordAiModerationPolicy,
    saveDiscordAiModerationPolicy,
    saveDiscordChannelPurpose,
    loadDiscordWelcomeSettings,
    saveDiscordWelcomeSettings,
    resetDiscordConnectionDetails,
    loadPlatformHealth,
    resetPlatformDashboard,
  };
}
