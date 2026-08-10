<script setup lang="ts">
import { onMounted, ref } from "vue";
import { consoleApi, ConsoleApiError } from "./api/consoleApi";
import { useBrowserSession } from "./features/auth/useBrowserSession";
import { useControlModules } from "./features/modules/useControlModules";
import { useOrganizations } from "./features/organizations/useOrganizations";

const email = ref("");
const password = ref("");
const organizationName = ref("");
const busy = ref(false);
const notice = ref("");
const platform = ref<"discord" | "twitch" | "telegram">("discord");
const externalResourceId = ref("");
const connections = ref<PlatformConnection[]>([]);
const platformHealth = ref<PlatformHealth | null>(null);
const browserSession = useBrowserSession();
const sessionState = browserSession.state;
const organizationDirectory = useOrganizations();
const organizationState = organizationDirectory.state;
const organizations = organizationDirectory.items;
const organizationId = organizationDirectory.selectedId;
const moduleCatalog = useControlModules();

onMounted(() => {
  void restoreConsoleSession();
});

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

async function restoreConsoleSession() {
  const restoredState = await browserSession.refresh();
  if (restoredState === "authenticated") await loadOrganizationsAndWorkspace();
}

async function signIn() {
  busy.value = true;
  notice.value = "";
  try {
    await consoleApi<void>("/api/v1/auth/email-password/sessions", {
      method: "POST",
      body: JSON.stringify({ email: email.value, password: password.value }),
    });
    const restoredState = await browserSession.refresh();
    password.value = "";
    if (restoredState === "authenticated") {
      await loadOrganizationsAndWorkspace();
      notice.value = "Signed in to Muxivo Console.";
    } else {
      notice.value = "Sign-in succeeded, but the Console session could not be restored.";
    }
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function signOut() {
  busy.value = true;
  notice.value = "";
  clearWorkspaceState();
  const state = await browserSession.signOut();
  notice.value =
    state === "anonymous"
      ? "Signed out of Muxivo Console."
      : "Sign-out could not be confirmed. Console access is hidden until the session is checked.";
  busy.value = false;
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
    organizationDirectory.addAndSelect({ ...organization, role: "owner" });
    await loadSelectedWorkspace();
    notice.value = `Organization ${organization.name} is ready (${organization.slug}).`;
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadOrganizationsAndWorkspace() {
  clearPlatformState();
  const state = await organizationDirectory.load();
  if (state === "ready" && organizationId.value) await loadSelectedWorkspace();
}

async function loadMoreOrganizations() {
  await organizationDirectory.loadMore();
}

async function selectOrganization(event: Event) {
  const selectedId = (event.target as HTMLSelectElement).value;
  if (!organizationDirectory.select(selectedId)) return;
  await loadSelectedWorkspace();
}

async function loadSelectedWorkspace() {
  clearPlatformState();
  if (!organizationId.value) return;
  await Promise.all([loadConnections(), moduleCatalog.load(organizationId.value)]);
}

async function loadConnections() {
  if (!organizationId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    const payload = await consoleApi<{ items: PlatformConnection[] }>(
      `/api/v1/organizations/${encodeURIComponent(organizationId.value)}/platform-connections`,
    );
    connections.value = payload.items;
    platformHealth.value = null;
  } catch (error) {
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function loadDiscordHealth() {
  if (!organizationId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    platformHealth.value = await consoleApi<PlatformHealth>(
      `/api/v1/organizations/${encodeURIComponent(organizationId.value)}/platforms/discord/health`,
    );
  } catch (error) {
    platformHealth.value = null;
    notice.value = messageFor(error);
  } finally {
    busy.value = false;
  }
}

async function registerConnection() {
  if (!organizationId.value) return;
  busy.value = true;
  notice.value = "";
  try {
    const connection = await consoleApi<PlatformConnection>(
      `/api/v1/organizations/${encodeURIComponent(organizationId.value)}/platform-connections`,
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

function clearPlatformState() {
  externalResourceId.value = "";
  connections.value = [];
  platformHealth.value = null;
  moduleCatalog.clear();
}

function clearWorkspaceState() {
  organizationDirectory.clear();
  clearPlatformState();
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
    <section v-if="sessionState === 'checking'" class="card" aria-live="polite">
      <h2>Restoring your session</h2>
      <p>Checking the first-party Muxivo Console session.</p>
    </section>
    <section v-else-if="sessionState === 'unavailable'" class="card" role="alert">
      <h2>Console is temporarily unavailable</h2>
      <p>Your sign-in state could not be verified. No platform access has been granted.</p>
      <button type="button" :disabled="busy" @click="restoreConsoleSession">Retry</button>
    </section>
    <section v-else-if="sessionState === 'anonymous'" class="card">
      <h2>Sign in</h2>
      <form @submit.prevent="signIn"><label>Email<input v-model="email" type="email" autocomplete="email" required /></label><label>Password<input v-model="password" type="password" autocomplete="current-password" minlength="12" required /></label><button :disabled="busy">{{ busy ? "Signing in…" : "Sign in" }}</button></form>
    </section>
    <template v-else>
      <section class="card">
        <div class="section-heading">
          <div><h2>Organizations</h2><p>Choose the tenant whose platform resources you are allowed to manage.</p></div>
          <button type="button" :disabled="busy" @click="signOut">{{ busy ? "Working…" : "Sign out" }}</button>
        </div>
        <div v-if="organizationState === 'loading'" class="directory-state" aria-live="polite">Loading your organizations…</div>
        <div v-else-if="organizationState === 'unavailable'" class="directory-state" role="alert">
          <p>Organization access could not be verified. Platform controls stay hidden.</p>
          <button type="button" :disabled="busy" @click="loadOrganizationsAndWorkspace">Retry organizations</button>
        </div>
        <div v-else-if="organizationState === 'ready'" class="organization-switcher">
          <label>Current organization
            <select :value="organizationId" :disabled="busy" @change="selectOrganization">
              <option v-for="organization in organizations" :key="organization.id" :value="organization.id">
                {{ organization.name }} · {{ organization.role }}
              </option>
            </select>
          </label>
          <button v-if="organizationDirectory.nextCursor.value" type="button" :disabled="organizationDirectory.loadingMore.value" @click="loadMoreOrganizations">
            {{ organizationDirectory.loadingMore.value ? "Loading…" : "Load more" }}
          </button>
        </div>
        <p v-else-if="organizationState === 'empty'" class="directory-state">You do not belong to an organization yet. Create the first one below.</p>
        <form class="create-organization" @submit.prevent="createOrganization"><label>New organization name<input v-model="organizationName" maxlength="128" required /></label><button :disabled="busy">{{ busy ? "Creating…" : "Create organization" }}</button></form>
        <div class="identity-link"><h3>Discord identity</h3><p>Link your Discord account before registering a Discord server connection. Discord remains the authority for server-native access.</p><button type="button" :disabled="busy" @click="linkDiscord">Link Discord</button></div>
      </section>
      <section v-if="organizationState === 'ready' && organizationId" class="card workspace">
        <div class="section-heading"><div><h2>Control modules</h2><p>Browser-ready capabilities are discovered through the Console BFF and each platform's versioned Control API.</p></div><span v-if="organizationDirectory.selected.value" class="role-badge">{{ organizationDirectory.selected.value.role }}</span></div>
        <p v-if="moduleCatalog.state.value === 'loading'" class="directory-state">Loading authorized modules…</p>
        <p v-else-if="moduleCatalog.state.value === 'unavailable'" class="directory-state">Control modules are temporarily unavailable. No capability has been assumed.</p>
        <p v-else-if="moduleCatalog.state.value === 'empty'" class="directory-state">No browser-ready modules are exposed for this organization yet.</p>
        <ul v-else-if="moduleCatalog.state.value === 'ready'" class="module-grid">
          <li v-for="module in moduleCatalog.items.value" :key="module.key">
            <div><span class="module-platform">{{ module.platform }}</span><strong>{{ module.display_name }}</strong><small>{{ module.key }}</small></div>
            <div class="module-meta"><span>{{ module.capability }}</span><em :data-status="module.status">{{ module.status.replaceAll("_", " ") }}</em></div>
          </li>
        </ul>
      </section>
      <section v-if="organizationState === 'ready' && organizationId" class="card workspace">
        <div class="section-heading"><div><h2>Platform connections</h2><p>Connections belong to the selected organization. Platform services independently verify ownership and capability.</p></div></div>
        <form class="connection-form" @submit.prevent="registerConnection"><label>Platform<select v-model="platform"><option value="discord">Discord</option><option value="twitch">Twitch</option><option value="telegram">Telegram</option></select></label><label>External resource ID<input v-model="externalResourceId" required /></label><button :disabled="busy">Register connection</button></form>
        <ul v-if="connections.length" class="connections"><li v-for="connection in connections" :key="connection.id"><strong>{{ connection.platform }}</strong><span>{{ connection.external_resource_id }}</span><em :data-status="connection.status">{{ connection.status.replaceAll("_", " ") }}</em></li></ul>
        <p v-else class="empty-state">No platform connections are visible for this organization.</p>
        <section class="platform-health" aria-labelledby="discord-health-heading">
          <div class="section-heading"><div><h3 id="discord-health-heading">Discord platform health</h3><p>Read-only runtime signals are requested through the Console BFF; Discord credentials never enter the browser.</p></div><button type="button" :disabled="busy" @click="loadDiscordHealth">{{ busy ? "Loading…" : "Load health" }}</button></div>
          <ul v-if="platformHealth" class="health-signals"><li v-for="signal in platformHealth.signals" :key="signal.key"><span><strong>{{ signal.display_name }}</strong><small>{{ signal.value }}</small></span><em :data-status="signal.status">{{ signal.status }}</em></li></ul>
        </section>
      </section>
    </template>
    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
  </main>
</template>
