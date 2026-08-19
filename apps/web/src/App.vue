<script setup lang="ts">
import { computed, ref } from "vue";
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
const selectedDiscordConnectionId = ref("");
const dashboardSummary = ref<PlatformDashboardSummary | null>(null);
const channelCatalog = ref<PlatformChannelCatalog | null>(null);
const welcomeSettings = ref<PlatformWelcomeSettings | null>(null);

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
type PlatformDashboardSummary = {
  organization_id: string;
  connection_id: string;
  platform: "discord";
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
  platform: "discord";
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

const usableDiscordConnections = computed(() =>
  connections.value.filter(
    (connection) =>
      connection.platform === "discord" &&
      (connection.status === "active" || connection.status === "degraded"),
  ),
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
    dashboardSummary.value = null;
    channelCatalog.value = null;
    welcomeSettings.value = null;
    selectedDiscordConnectionId.value = usableDiscordConnections.value[0]?.id ?? "";
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
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
}

async function loadDiscordHealth() {
  if (!organizationId.value.trim()) return;
  busy.value = true;
  notice.value = "";
  try {
    platformHealth.value = await consoleApi<PlatformHealth>(
      `/api/v1/organizations/${encodeURIComponent(organizationId.value.trim())}/platforms/discord/health`,
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
    </section>
    <section v-else class="card">
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
      <section v-if="organizationId" class="platform-health" aria-labelledby="discord-health-heading">
        <div class="section-heading"><div><h3 id="discord-health-heading">Discord platform health</h3><p>Read-only runtime signals are requested through the Console BFF; Discord credentials never enter the browser.</p></div><button type="button" :disabled="busy" @click="loadDiscordHealth">{{ busy ? "Loading…" : "Load health" }}</button></div>
        <ul v-if="platformHealth" class="health-signals"><li v-for="signal in platformHealth.signals" :key="signal.key"><span><strong>{{ signal.display_name }}</strong><small>{{ signal.value }}</small></span><em :data-status="signal.status">{{ signal.status }}</em></li></ul>
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
      <section v-if="usableDiscordConnections.length" class="platform-dashboard" aria-labelledby="discord-welcome-heading">
        <div class="section-heading"><div><h3 id="discord-welcome-heading">Discord welcome settings</h3><p>Read-only view of the existing Discord Activity welcome configuration. Editing and test sends remain in Activity for now.</p></div><button type="button" :disabled="busy || !selectedDiscordConnectionId" @click="loadDiscordWelcomeSettings">{{ busy ? "Loading…" : "Load welcome settings" }}</button></div>
        <form v-if="welcomeSettings" class="welcome-settings" @submit.prevent="saveDiscordWelcomeSettings"><label><input v-model="welcomeSettings.is_enabled" type="checkbox" /> Welcome enabled</label><label>Title<input v-model="welcomeSettings.title" maxlength="256" required /></label><label>Description<textarea v-model="welcomeSettings.description" maxlength="4096" required></textarea></label><label>Color<input v-model.number="welcomeSettings.color" type="number" min="0" max="16777215" required /></label><label>Rules channel ID<input v-model="welcomeSettings.rules_channel_id" inputmode="numeric" /></label><label>Roles channel ID<input v-model="welcomeSettings.roles_channel_id" inputmode="numeric" /></label><p>Changes are re-authorized by Discord and recorded in Discord Activity.</p><button :disabled="busy">{{ busy ? "Saving…" : "Save welcome settings" }}</button></form>
      </section>
    </section>
    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
  </main>
</template>
