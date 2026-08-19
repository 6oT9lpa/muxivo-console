<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { consoleApi, ConsoleApiError } from "./api/consoleApi";

const email = ref("");
const password = ref("");
const organizationName = ref("");
const authenticated = ref(false);
const busy = ref(false);
const notice = ref("");
const organizationId = ref("");
const platform = ref<"discord" | "twitch" | "telegram">("discord");
const externalResourceId = ref("");
const connections = ref<PlatformConnection[]>([]);
const platformHealth = ref<PlatformHealth | null>(null);
const controlModules = ref<ControlModule[]>([]);
const selectedConnectionId = ref("");
const selectedDiscordConnectionId = ref("");
const dashboardSummary = ref<PlatformDashboardSummary | null>(null);
const channelCatalog = ref<PlatformChannelCatalog | null>(null);
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

type Organization = { id: string; name: string; slug: string };
type PlatformConnection = {
  id: string;
  organization_id: string;
  platform: "discord" | "twitch" | "telegram";
  external_resource_id: string;
  status: "pending" | "active" | "degraded" | "reauth_required" | "disconnected";
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
const selectedConnection = computed(() =>
  usableConnections.value.find((connection) => connection.id === selectedConnectionId.value) ?? null,
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
    password.value = "";
    notice.value = "Signed in to Muxivo Console.";
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

async function signOut() {
  busy.value = true;
  notice.value = "";
  try {
    await consoleApi<void>("/api/v1/auth/session", { method: "DELETE" });
    authenticated.value = false;
    connections.value = [];
    organizationId.value = "";
    notice.value = "Signed out of Muxivo Console.";
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

onMounted(async () => {
  try {
    await consoleApi<{ authenticated: boolean }>("/api/v1/auth/session");
    authenticated.value = true;
  } catch {
    // A missing session is the normal first-visit state.
  }
});

async function linkDiscord() {
  busy.value = true;
  notice.value = "";
  try {
    const authorization = await consoleApi<{ authorization_url: string }>(
      "/api/v1/identity-links/discord/authorizations",
      { method: "POST" },
    );
    window.location.assign(authorization.authorization_url);
  } catch (error) {
    notice.value = messageFor(error);
    busy.value = false;
  }
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
    organizationId.value = organization.id;
    notice.value = `Organization ${organization.name} is ready (${organization.slug}).`;
    await loadConnections();
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadConnections() {
  if (!organizationId.value.trim()) return;
  busy.value = true;
  notice.value = "";
  try {
    const payload = await consoleApi<{ items: PlatformConnection[] }>(
      `/api/v1/organizations/${encodeURIComponent(organizationId.value.trim())}/platform-connections`,
    );
    connections.value = payload.items;
    platformHealth.value = null;
    controlModules.value = [];
    dashboardSummary.value = null;
    channelCatalog.value = null;
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

async function loadControlModules() {
  if (!organizationId.value.trim()) return;
  busy.value = true;
  notice.value = "";
  try {
    const payload = await consoleApi<{ items: ControlModule[] }>(
      `/api/v1/organizations/${encodeURIComponent(organizationId.value.trim())}/control-modules`,
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
  if (!organizationId.value.trim() || !selectedConnectionId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    dashboardSummary.value = await consoleApi<PlatformDashboardSummary>(
      `/api/v1/organizations/${encodeURIComponent(organizationId.value.trim())}/platform-connections/${encodeURIComponent(selectedConnectionId.value)}/dashboard`,
    );
  } catch (error) {
    dashboardSummary.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadPlatformChannels() {
  if (!organizationId.value.trim() || !selectedConnectionId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    channelCatalog.value = await consoleApi<PlatformChannelCatalog>(
      `/api/v1/organizations/${encodeURIComponent(organizationId.value.trim())}/platform-connections/${encodeURIComponent(selectedConnectionId.value)}/channels`,
    );
  } catch (error) {
    channelCatalog.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

function selectPlatformConnection() {
  dashboardSummary.value = null;
  channelCatalog.value = null;
  platformHealth.value = null;
}

async function loadDiscordDashboard() {
  if (!organizationId.value.trim() || !selectedDiscordConnectionId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    dashboardSummary.value = await consoleApi<PlatformDashboardSummary>(
      `/api/v1/organizations/${encodeURIComponent(organizationId.value.trim())}/platform-connections/${encodeURIComponent(selectedDiscordConnectionId.value)}/dashboard`,
    );
  } catch (error) {
    dashboardSummary.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadOrganizationAuditEvents(nextPage = false) {
  if (!organizationId.value.trim()) return;
  if (nextPage && !auditEventsNextCursor.value) return;
  busy.value = true;
  notice.value = "";
  try {
    const query = nextPage ? `?after=${encodeURIComponent(auditEventsNextCursor.value ?? "")}` : "";
    const page = await consoleApi<AuditEventPage>(
      `/api/v1/organizations/${encodeURIComponent(organizationId.value.trim())}/audit-events${query}`,
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
  if (!organizationId.value.trim() || !selectedDiscordConnectionId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    channelCatalog.value = await consoleApi<PlatformChannelCatalog>(
      `/api/v1/organizations/${encodeURIComponent(organizationId.value.trim())}/platform-connections/${encodeURIComponent(selectedDiscordConnectionId.value)}/channels`,
    );
  } catch (error) {
    channelCatalog.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadDiscordChannelPurposes() {
  if (!organizationId.value.trim() || !selectedDiscordConnectionId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    channelPurposes.value = await consoleApi<PlatformChannelPurposes>(
      `/api/v1/organizations/${encodeURIComponent(organizationId.value.trim())}/platform-connections/${encodeURIComponent(selectedDiscordConnectionId.value)}/channel-purposes`,
    );
  } catch (error) {
    channelPurposes.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadDiscordAiModerationSummary() {
  if (!organizationId.value.trim() || !selectedDiscordConnectionId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    aiModerationSummary.value = await consoleApi<PlatformAiModerationSummary>(
      `/api/v1/organizations/${encodeURIComponent(organizationId.value.trim())}/platform-connections/${encodeURIComponent(selectedDiscordConnectionId.value)}/ai-moderation-summary`,
    );
  } catch (error) {
    aiModerationSummary.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadDiscordAiModerationPolicy() {
  if (!organizationId.value.trim() || !selectedDiscordConnectionId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    const state = await consoleApi<PlatformAiModerationPolicyState>(
      `/api/v1/organizations/${encodeURIComponent(organizationId.value.trim())}/platform-connections/${encodeURIComponent(selectedDiscordConnectionId.value)}/ai-moderation-policy`,
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
  if (!organizationId.value.trim() || !selectedDiscordConnectionId.value || !aiModerationPolicy.value) return;
  busy.value = true;
  notice.value = "";
  try {
    const policy = {
      ...aiModerationPolicy.value.policy,
      blacklist_words: splitPolicyValues(aiModerationBlacklistWords.value),
      allowed_domains: splitPolicyValues(aiModerationAllowedDomains.value),
    };
    aiModerationSummary.value = await consoleApi<PlatformAiModerationSummary>(
      `/api/v1/organizations/${encodeURIComponent(organizationId.value.trim())}/platform-connections/${encodeURIComponent(selectedDiscordConnectionId.value)}/ai-moderation-policy`,
      { method: "PUT", body: JSON.stringify(policy) },
    );
    aiModerationPolicy.value = { ...aiModerationPolicy.value, policy, is_default_policy: false };
    notice.value = "Discord AI moderation policy saved.";
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
  if (!organizationId.value.trim() || !selectedDiscordConnectionId.value || !selectedPurposeChannelId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    channelPurposes.value = await consoleApi<PlatformChannelPurposes>(
      `/api/v1/organizations/${encodeURIComponent(organizationId.value.trim())}/platform-connections/${encodeURIComponent(selectedDiscordConnectionId.value)}/channel-purposes`,
      { method: "PUT", body: JSON.stringify({ purpose: selectedPurpose.value, channel_id: selectedPurposeChannelId.value }) },
    );
    notice.value = "Discord channel purpose saved.";
  } catch (error) { notice.value = messageFor(error); } finally { busy.value = false; }
}

async function loadDiscordWelcomeSettings() {
  if (!organizationId.value.trim() || !selectedDiscordConnectionId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    welcomeSettings.value = await consoleApi<PlatformWelcomeSettings>(
      `/api/v1/organizations/${encodeURIComponent(organizationId.value.trim())}/platform-connections/${encodeURIComponent(selectedDiscordConnectionId.value)}/welcome-settings`,
    );
  } catch (error) {
    welcomeSettings.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function saveDiscordWelcomeSettings() {
  if (!organizationId.value.trim() || !selectedDiscordConnectionId.value || !welcomeSettings.value) return;
  busy.value = true;
  notice.value = "";
  try {
    const settings = welcomeSettings.value;
    welcomeSettings.value = await consoleApi<PlatformWelcomeSettings>(
      `/api/v1/organizations/${encodeURIComponent(organizationId.value.trim())}/platform-connections/${encodeURIComponent(selectedDiscordConnectionId.value)}/welcome-settings`,
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
    notice.value = "Discord welcome settings saved.";
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
  if (!organizationId.value.trim() || !selectedConnection.value) return;
  busy.value = true;
  notice.value = "";
  try {
    platformHealth.value = await consoleApi<PlatformHealth>(
      `/api/v1/organizations/${encodeURIComponent(organizationId.value.trim())}/platforms/${selectedConnection.value.platform}/health`,
    );
  } catch (error) {
    platformHealth.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function registerConnection() {
  if (!organizationId.value.trim()) return;
  busy.value = true;
  notice.value = "";
  try {
    const connection = await consoleApi<PlatformConnection>(
      `/api/v1/organizations/${encodeURIComponent(organizationId.value.trim())}/platform-connections`,
      {
        method: "POST",
        body: JSON.stringify({ platform: platform.value, external_resource_id: externalResourceId.value }),
      },
    );
    externalResourceId.value = "";
    connections.value = [connection, ...connections.value];
    notice.value = `${connection.platform} connection is pending verification.`;
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

function messageFor(error: unknown): string {
  if (error instanceof ConsoleApiError && error.status === 401) return "Email or password is incorrect.";
  if (error instanceof ConsoleApiError && error.status === 403) return "Your current session cannot perform this action.";
  return "Console is temporarily unavailable. Please try again.";
}
</script>

<template>
  <main class="shell">
    <header><span class="eyebrow">MUXIVO</span><h1>Console</h1><p>One browser control plane for every Muxivo bot platform.</p></header>
    <section v-if="!authenticated" class="card">
      <h2>Sign in</h2>
      <form @submit.prevent="signIn"><label>Email<input v-model="email" type="email" autocomplete="email" required /></label><label>Password<input v-model="password" type="password" autocomplete="current-password" minlength="12" required /></label><button :disabled="busy">{{ busy ? "Signing in…" : "Sign in" }}</button></form>
      <div class="identity-link"><h3>Or continue with Discord</h3><p>Discord signs in only to an account you have already linked.</p><button type="button" :disabled="busy" @click="signInWithDiscord">Sign in with Discord</button></div>
    </section>
    <section v-else class="card">
      <div class="section-heading"><h2>Workspace</h2><button type="button" :disabled="busy" @click="signOut">Sign out</button></div>
      <h2>Create an organization</h2>
      <p>Organizations own Console memberships and platform connections; bot credentials stay with their platform services.</p>
      <form @submit.prevent="createOrganization"><label>Name<input v-model="organizationName" maxlength="128" required /></label><button :disabled="busy">{{ busy ? "Creating…" : "Create organization" }}</button></form>
      <div class="identity-link"><h3>Discord identity</h3><p>Link your Discord account before registering a Discord server connection. Discord remains the authority for your server access.</p><button type="button" :disabled="busy" @click="linkDiscord">Link Discord</button></div>
    </section>
    <section v-if="authenticated" class="card workspace">
      <h2>Platform connections</h2>
      <p>Choose an organization, then connect a platform resource. The platform service independently verifies the request.</p>
      <form @submit.prevent="loadConnections"><label>Organization ID<input v-model="organizationId" inputmode="text" placeholder="UUID" required /></label><button :disabled="busy">{{ busy ? "Loading…" : "Load connections" }}</button></form>
      <form v-if="organizationId" class="connection-form" @submit.prevent="registerConnection"><label>Platform<select v-model="platform"><option value="discord">Discord</option><option value="twitch">Twitch</option><option value="telegram">Telegram</option></select></label><label>External resource ID<input v-model="externalResourceId" required /></label><button :disabled="busy">Register connection</button></form>
      <ul v-if="connections.length" class="connections"><li v-for="connection in connections" :key="connection.id"><strong>{{ connection.platform }}</strong><span>{{ connection.external_resource_id }}</span><em :data-status="connection.status">{{ connection.status.replaceAll("_", " ") }}</em></li></ul>
      <section v-if="organizationId" class="platform-dashboard" aria-labelledby="control-modules-heading">
        <div class="section-heading"><div><h3 id="control-modules-heading">Available bot modules</h3><p>Each platform advertises browser-ready capabilities through its Control API. Unsupported features stay unavailable rather than being emulated in Console.</p></div><button type="button" :disabled="busy" @click="loadControlModules">{{ busy ? "Loading…" : "Load modules" }}</button></div>
        <ul v-if="controlModules.length" class="health-signals"><li v-for="module in controlModules" :key="module.key"><span><strong>{{ module.display_name }}</strong><small>{{ module.platform }} · {{ module.capability }}</small></span><em :data-status="module.status">{{ module.status.replaceAll("_", " ") }}</em></li></ul>
      </section>
      <section v-if="usableConnections.length" class="platform-dashboard" aria-labelledby="platform-activity-heading">
        <div class="section-heading"><div><h3 id="platform-activity-heading">Platform activity</h3><p>Common browser controls use a selected connection's platform adapter. Platform credentials never enter the browser.</p></div></div>
        <label class="connection-picker">Connection<select v-model="selectedConnectionId" @change="selectPlatformConnection"><option v-for="connection in usableConnections" :key="connection.id" :value="connection.id">{{ connection.platform }} · {{ connection.external_resource_id }} · {{ connection.status }}</option></select></label>
        <div class="section-heading"><div><h4>Dashboard summary</h4><p>Safe aggregate counters for the selected bot connection.</p></div><button type="button" :disabled="busy || !selectedConnectionId" @click="loadPlatformDashboard">{{ busy ? "Loading…" : "Load summary" }}</button></div>
        <dl v-if="dashboardSummary" class="dashboard-metrics"><div><dt>Messages today</dt><dd>{{ dashboardSummary.messages_today }}</dd></div><div><dt>AI flagged today</dt><dd>{{ dashboardSummary.ai_flagged_today }}</dd></div><div><dt>Creator sources</dt><dd>{{ dashboardSummary.creator_sources }}</dd></div><div><dt>Bot latency</dt><dd>{{ dashboardSummary.bot_latency_ms === null ? "Unavailable" : `${dashboardSummary.bot_latency_ms} ms` }}</dd></div></dl>
        <div class="section-heading"><div><h4>Channels</h4><p>Generic resources supplied by the selected platform adapter.</p></div><button type="button" :disabled="busy || !selectedConnectionId" @click="loadPlatformChannels">{{ busy ? "Loading…" : "Load channels" }}</button></div>
        <ul v-if="channelCatalog?.items.length" class="health-signals"><li v-for="channel in channelCatalog.items" :key="channel.id"><span><strong>{{ channel.name }}</strong><small>{{ channel.kind }}</small></span></li></ul>
      </section>
      <section v-if="selectedConnection" class="platform-health" aria-labelledby="platform-health-heading">
        <div class="section-heading"><div><h3 id="platform-health-heading">{{ selectedConnection.platform }} platform health</h3><p>Read-only runtime signals are requested through the Console BFF; platform credentials never enter the browser.</p></div><button type="button" :disabled="busy" @click="loadPlatformHealth">{{ busy ? "Loading…" : "Load health" }}</button></div>
        <ul v-if="platformHealth" class="health-signals"><li v-for="signal in platformHealth.signals" :key="signal.key"><span><strong>{{ signal.display_name }}</strong><small>{{ signal.value }}</small></span><em :data-status="signal.status">{{ signal.status }}</em></li></ul>
      </section>
      <section v-if="organizationId" class="platform-dashboard" aria-labelledby="organization-audit-heading">
        <div class="section-heading"><div><h3 id="organization-audit-heading">Organization audit log</h3><p>Secret-free Console audit facts. Platform tokens, message content and internal metadata are never displayed here.</p></div><button type="button" :disabled="busy" @click="loadOrganizationAuditEvents()">{{ busy ? "Loading…" : "Load audit log" }}</button></div>
        <ul v-if="auditEvents.length" class="health-signals audit-events"><li v-for="event in auditEvents" :key="event.id"><span><strong>{{ event.action }}</strong><small>{{ new Date(event.created_at).toLocaleString() }} · {{ event.resource_type }}{{ event.resource_id ? ` · ${event.resource_id}` : "" }}</small></span><em :data-status="event.result">{{ event.result }}</em></li></ul>
        <p v-else-if="!busy">No audit events loaded.</p>
        <button v-if="auditEventsNextCursor" class="load-more" type="button" :disabled="busy" @click="loadOrganizationAuditEvents(true)">Load older events</button>
      </section>
      <section v-if="usableDiscordConnections.length" class="platform-dashboard" aria-labelledby="discord-dashboard-heading">
        <div class="section-heading"><div><h3 id="discord-dashboard-heading">Discord dashboard summary</h3><p>Safe aggregate counters for a Console-owned Discord connection. Audit details remain in Discord Activity.</p></div><button type="button" :disabled="busy || !selectedDiscordConnectionId" @click="loadDiscordDashboard">{{ busy ? "Loading…" : "Load summary" }}</button></div>
        <label class="connection-picker">Discord connection<select v-model="selectedDiscordConnectionId" @change="selectDiscordConnection"><option v-for="connection in usableDiscordConnections" :key="connection.id" :value="connection.id">{{ connection.external_resource_id }} · {{ connection.status }}</option></select></label>
        <dl v-if="dashboardSummary" class="dashboard-metrics"><div><dt>Messages today</dt><dd>{{ dashboardSummary.messages_today }}</dd></div><div><dt>AI flagged today</dt><dd>{{ dashboardSummary.ai_flagged_today }}</dd></div><div><dt>Creator sources</dt><dd>{{ dashboardSummary.creator_sources }}</dd></div><div><dt>Bot latency</dt><dd>{{ dashboardSummary.bot_latency_ms === null ? "Unavailable" : `${dashboardSummary.bot_latency_ms} ms` }}</dd></div></dl>
      </section>
      <section v-if="usableDiscordConnections.length" class="platform-dashboard" aria-labelledby="discord-channels-heading">
        <div class="section-heading"><div><h3 id="discord-channels-heading">Discord channels</h3><p>Generic channel resources for the selected connection. Configuration changes are not available yet.</p></div><button type="button" :disabled="busy || !selectedDiscordConnectionId" @click="loadDiscordChannels">{{ busy ? "Loading…" : "Load channels" }}</button></div>
        <ul v-if="channelCatalog?.items.length" class="health-signals"><li v-for="channel in channelCatalog.items" :key="channel.id"><span><strong>{{ channel.name }}</strong><small>{{ channel.kind }}</small></span></li></ul>
        <p v-else-if="channelCatalog && !channelCatalog.items.length">No browser-ready channels are available for this connection.</p>
      </section>
      <section v-if="usableDiscordConnections.length" class="platform-dashboard" aria-labelledby="discord-channel-purposes-heading">
        <div class="section-heading"><div><h3 id="discord-channel-purposes-heading">Discord channel purposes</h3><p>Current Activity assignments. Purpose changes will be enabled after the dedicated write contract is complete.</p></div><button type="button" :disabled="busy || !selectedDiscordConnectionId" @click="loadDiscordChannelPurposes">{{ busy ? "Loading…" : "Load assignments" }}</button></div>
        <ul v-if="channelPurposes?.items.length" class="health-signals"><li v-for="assignment in channelPurposes.items" :key="assignment.purpose"><span><strong>{{ assignment.purpose }}</strong><small>{{ assignment.channel_id }}</small></span></li></ul>
        <form v-if="channelCatalog?.items.length" @submit.prevent="saveDiscordChannelPurpose"><label>Purpose<select v-model="selectedPurpose"><option value="welcome">Welcome</option><option value="member_log">Member log</option><option value="mod_log">Moderation log</option><option value="message_log">Message log</option><option value="channel_log">Channel log</option><option value="stream_announce">Stream announcements</option><option value="dev_blog">Dev blog</option><option value="ai_moderation_log">AI moderation log</option></select></label><label>Text channel<select v-model="selectedPurposeChannelId" required><option disabled value="">Select channel</option><option v-for="channel in channelCatalog.items.filter((item) => item.kind === 'text')" :key="channel.id" :value="channel.id">{{ channel.name }}</option></select></label><button :disabled="busy">{{ busy ? "Saving…" : "Save assignment" }}</button></form>
      </section>
      <section v-if="usableDiscordConnections.length" class="platform-dashboard" aria-labelledby="discord-ai-moderation-heading">
        <div class="section-heading"><div><h3 id="discord-ai-moderation-heading">Discord AI moderation</h3><p>Policy is read and saved through Console. Review queue, message content and simulations remain in Discord Activity.</p></div><button type="button" :disabled="busy || !selectedDiscordConnectionId" @click="loadDiscordAiModerationSummary">{{ busy ? "Loading…" : "Load policy summary" }}</button></div>
        <dl v-if="aiModerationSummary" class="dashboard-metrics"><div><dt>Mode</dt><dd>{{ aiModerationSummary.enforcement_mode }}</dd></div><div><dt>Test mode</dt><dd>{{ aiModerationSummary.test_mode ? "Enabled" : "Disabled" }}</dd></div><div><dt>Covered channels</dt><dd>{{ aiModerationSummary.covered_channel_count }}</dd></div><div><dt>Labels</dt><dd>{{ aiModerationSummary.label_count }}</dd></div><div><dt>Log channel</dt><dd>{{ aiModerationSummary.log_channel_configured ? "Configured" : "Not configured" }}</dd></div><div><dt>Automatic actions</dt><dd>{{ aiModerationSummary.automated_timeout_enabled || aiModerationSummary.automated_kick_enabled || aiModerationSummary.automated_ban_enabled ? "Enabled" : "Disabled" }}</dd></div></dl>
        <div class="section-heading policy-heading"><div><h4>Policy editor</h4><p>Loading and saving requires current Discord administrator authority. All untouched rules are preserved.</p></div><button type="button" :disabled="busy || !selectedDiscordConnectionId" @click="loadDiscordAiModerationPolicy">{{ busy ? "Loading…" : "Load editable policy" }}</button></div>
        <form v-if="aiModerationPolicy" class="welcome-settings policy-settings" @submit.prevent="saveDiscordAiModerationPolicy">
          <p v-if="aiModerationPolicy.is_default_policy">This server currently uses the Discord Activity default policy. Saving creates its own explicit policy.</p>
          <label>Enforcement mode<select v-model="aiModerationPolicy.policy.enforcement_mode"><option value="SHADOW">Shadow — recommendations only</option><option value="LIMITED">Limited — confidence-capped enforcement</option><option value="ELEVATED">Elevated — explicit automated actions</option></select></label>
          <label><input v-model="aiModerationPolicy.policy.test_mode" type="checkbox" /> Test mode</label>
          <label>Limited minimum confidence<input v-model.number="aiModerationPolicy.policy.limited_min_confidence" type="number" min="0" max="1" step="0.01" required /></label>
          <label>Blacklist words<textarea v-model="aiModerationBlacklistWords" maxlength="50000" placeholder="One word or phrase per line"></textarea></label>
          <label>Allowed domains<textarea v-model="aiModerationAllowedDomains" maxlength="50000" placeholder="One domain per line"></textarea></label>
          <label><input v-model="aiModerationPolicy.policy.ocr_enabled" type="checkbox" /> Enable OCR analysis</label>
          <label>OCR failure mode<select v-model="aiModerationPolicy.policy.ocr_failure_mode"><option value="SKIP">Skip image</option><option value="REVIEW">Send to review</option></select></label>
          <fieldset><legend>Elevated automatic actions</legend><label><input v-model="aiModerationPolicy.policy.allow_automated_timeout" type="checkbox" /> Allow timeouts</label><label><input v-model="aiModerationPolicy.policy.allow_automated_kick" type="checkbox" /> Allow kicks</label><label><input v-model="aiModerationPolicy.policy.allow_automated_ban" type="checkbox" /> Allow bans</label><label><input v-model="aiModerationPolicy.policy.beta_enforcement_acknowledged" type="checkbox" /> I acknowledge elevated automatic-action risk</label></fieldset>
          <p>Saving rechecks Discord administrator authority, requires recent browser authentication and records an audit event. Label rules, exclusions and advanced thresholds remain intact unless changed in Discord Activity.</p>
          <button :disabled="busy">{{ busy ? "Saving…" : "Save AI moderation policy" }}</button>
        </form>
      </section>
      <section v-if="usableDiscordConnections.length" class="platform-dashboard" aria-labelledby="discord-welcome-heading">
        <div class="section-heading"><div><h3 id="discord-welcome-heading">Discord welcome settings</h3><p>Read-only view of the existing Discord Activity welcome configuration. Editing and test sends remain in Activity for now.</p></div><button type="button" :disabled="busy || !selectedDiscordConnectionId" @click="loadDiscordWelcomeSettings">{{ busy ? "Loading…" : "Load welcome settings" }}</button></div>
        <form v-if="welcomeSettings" class="welcome-settings" @submit.prevent="saveDiscordWelcomeSettings"><label><input v-model="welcomeSettings.is_enabled" type="checkbox" /> Welcome enabled</label><label>Title<input v-model="welcomeSettings.title" maxlength="256" required /></label><label>Description<textarea v-model="welcomeSettings.description" maxlength="4096" required></textarea></label><label>Color<input v-model.number="welcomeSettings.color" type="number" min="0" max="16777215" required /></label><label>Rules channel ID<input v-model="welcomeSettings.rules_channel_id" inputmode="numeric" /></label><label>Roles channel ID<input v-model="welcomeSettings.roles_channel_id" inputmode="numeric" /></label><p>Changes are re-authorized by Discord and recorded in Discord Activity.</p><button :disabled="busy">{{ busy ? "Saving…" : "Save welcome settings" }}</button></form>
      </section>
    </section>
    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
  </main>
</template>
