<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { consoleApi, ConsoleApiError } from "./api/consoleApi";
import { useBrowserSession } from "./features/auth/useBrowserSession";
import DashboardSummaryPanel from "./features/dashboard/DashboardSummaryPanel.vue";
import { useDashboardSummary } from "./features/dashboard/useDashboardSummary";
import { useControlModules } from "./features/modules/useControlModules";
import OrganizationMembersPanel from "./features/organizations/OrganizationMembersPanel.vue";
import { useOrganizationMembers } from "./features/organizations/useOrganizationMembers";
import {
  type OrganizationRole,
  useOrganizations,
} from "./features/organizations/useOrganizations";
import {
  type Platform,
  usePlatformAdapters,
} from "./features/platforms/usePlatformAdapters";

const email = ref("");
const password = ref("");
const organizationName = ref("");
const busy = ref(false);
const notice = ref("");
const platform = ref<Platform | "">("");
const externalResourceId = ref("");
const connections = ref<PlatformConnection[]>([]);
const platformHealth = ref<PlatformHealth | null>(null);
const browserSession = useBrowserSession();
const sessionState = browserSession.state;
const organizationDirectory = useOrganizations();
const organizationState = organizationDirectory.state;
const organizations = organizationDirectory.items;
const organizationId = organizationDirectory.selectedId;
const selectedOrganizationRole = computed(
  () => organizationDirectory.selected.value?.role ?? null,
);
const canViewOrganizationMembers = computed(
  () => selectedOrganizationRole.value === "owner" || selectedOrganizationRole.value === "admin",
);
const organizationMembers = useOrganizationMembers();
const platformAdapters = usePlatformAdapters();
const connectionPlatforms = platformAdapters.connectionPlatforms;
const moduleCatalog = useControlModules();
const dashboardSummary = useDashboardSummary();
let workspaceGeneration = 0;

onMounted(() => {
  void restoreConsoleSession();
});

type Organization = { id: string; name: string; slug: string };
type PlatformConnection = {
  id: string;
  organization_id: string;
  platform: Platform;
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
  platform: Platform;
  signals: PlatformHealthSignal[];
};

async function restoreConsoleSession() {
  const restoredState = await browserSession.refresh();
  if (restoredState === "authenticated") await loadAuthenticatedConsole();
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
      await loadAuthenticatedConsole();
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
  clearConsoleState();
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

async function loadAuthenticatedConsole() {
  invalidateWorkspace();
  const [adapterState, organizationState] = await Promise.all([
    platformAdapters.load(),
    organizationDirectory.load(),
  ]);
  if (adapterState === "ready") selectDefaultPlatform();
  if (organizationState === "ready" && organizationId.value) await loadSelectedWorkspace();
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
  const requestGeneration = ++workspaceGeneration;
  clearPlatformState();
  organizationMembers.clear();
  const targetOrganizationId = organizationId.value;
  if (!targetOrganizationId) return;

  const memberRequest = canViewOrganizationMembers.value
    ? organizationMembers.load(targetOrganizationId)
    : Promise.resolve("idle" as const);
  const [loadedConnections] = await Promise.all([
    loadConnections(targetOrganizationId, requestGeneration),
    moduleCatalog.load(targetOrganizationId),
    memberRequest,
  ]);
  if (!workspaceIsCurrent(targetOrganizationId, requestGeneration)) return;
  await loadDashboardModule(targetOrganizationId, loadedConnections);
}

async function loadMoreOrganizationMembers() {
  await organizationMembers.loadMore();
}

async function reloadOrganizationMembers() {
  const targetOrganizationId = organizationId.value;
  if (!targetOrganizationId || !canViewOrganizationMembers.value) return;
  await organizationMembers.load(targetOrganizationId);
}

async function changeOrganizationMemberRole(
  membershipId: string,
  role: OrganizationRole,
) {
  const targetOrganizationId = organizationId.value;
  const requestGeneration = workspaceGeneration;
  if (!targetOrganizationId) return;
  notice.value = "";
  const changed = await organizationMembers.changeRole(membershipId, role);
  if (!workspaceIsCurrent(targetOrganizationId, requestGeneration)) return;
  notice.value = changed
    ? "Organization member role updated."
    : "Role change was not applied. Reload the member list and try again.";
}

async function loadConnections(
  targetOrganizationId: string,
  requestGeneration: number,
): Promise<PlatformConnection[]> {
  busy.value = true;
  notice.value = "";
  try {
    const payload = await consoleApi<{ items: PlatformConnection[] }>(
      `/api/v1/organizations/${encodeURIComponent(targetOrganizationId)}/platform-connections`,
    );
    if (workspaceIsCurrent(targetOrganizationId, requestGeneration)) {
      connections.value = payload.items;
      platformHealth.value = null;
    }
    return payload.items;
  } catch (error) {
    if (workspaceIsCurrent(targetOrganizationId, requestGeneration)) notice.value = messageFor(error);
    return [];
  } finally {
    if (workspaceIsCurrent(targetOrganizationId, requestGeneration)) busy.value = false;
  }
}

async function loadDashboardModule(
  targetOrganizationId: string,
  loadedConnections: PlatformConnection[],
) {
  dashboardSummary.clear();
  if (!isControlModuleAvailable("discord.dashboard-summary")) return;
  const connection = loadedConnections.find(
    (item) =>
      item.platform === "discord" && (item.status === "active" || item.status === "degraded"),
  );
  if (!connection) return;
  await dashboardSummary.load(targetOrganizationId, connection.id);
}

async function loadDiscordHealth() {
  const targetOrganizationId = organizationId.value;
  const requestGeneration = workspaceGeneration;
  if (!targetOrganizationId) return;
  busy.value = true;
  notice.value = "";
  try {
    const health = await consoleApi<PlatformHealth>(
      `/api/v1/organizations/${encodeURIComponent(targetOrganizationId)}/platforms/discord/health`,
    );
    if (health.organization_id !== targetOrganizationId || health.platform !== "discord") {
      throw new Error("Platform health response does not match the selected resource");
    }
    if (workspaceIsCurrent(targetOrganizationId, requestGeneration)) platformHealth.value = health;
  } catch (error) {
    if (workspaceIsCurrent(targetOrganizationId, requestGeneration)) {
      platformHealth.value = null;
      notice.value = messageFor(error);
    }
  } finally {
    if (workspaceIsCurrent(targetOrganizationId, requestGeneration)) busy.value = false;
  }
}

async function registerConnection() {
  const targetOrganizationId = organizationId.value;
  const requestGeneration = workspaceGeneration;
  const targetPlatform = platform.value;
  if (
    !targetOrganizationId ||
    !targetPlatform ||
    !platformAdapters.supports(targetPlatform, "connection_registration")
  ) {
    return;
  }
  busy.value = true;
  notice.value = "";
  try {
    const connection = await consoleApi<PlatformConnection>(
      `/api/v1/organizations/${encodeURIComponent(targetOrganizationId)}/platform-connections`,
      {
        method: "POST",
        body: JSON.stringify({
          platform: targetPlatform,
          external_resource_id: externalResourceId.value,
        }),
      },
    );
    if (
      connection.organization_id !== targetOrganizationId ||
      connection.platform !== targetPlatform
    ) {
      throw new Error("Platform connection response does not match the selected request");
    }
    if (!workspaceIsCurrent(targetOrganizationId, requestGeneration)) return;
    externalResourceId.value = "";
    connections.value = [connection, ...connections.value];
    notice.value = `${connection.platform} connection is pending verification.`;
  } catch (error) {
    if (workspaceIsCurrent(targetOrganizationId, requestGeneration)) notice.value = messageFor(error);
  } finally {
    if (workspaceIsCurrent(targetOrganizationId, requestGeneration)) busy.value = false;
  }
}

function selectDefaultPlatform() {
  const firstSupported = connectionPlatforms.value[0] ?? "";
  if (!platform.value || !connectionPlatforms.value.includes(platform.value)) {
    platform.value = firstSupported;
  }
}

function isControlModuleAvailable(key: string): boolean {
  return moduleCatalog.items.value.some(
    (module) => module.key === key && module.status === "available",
  );
}

function workspaceIsCurrent(targetOrganizationId: string, requestGeneration: number): boolean {
  return requestGeneration === workspaceGeneration && organizationId.value === targetOrganizationId;
}

function invalidateWorkspace() {
  workspaceGeneration += 1;
  organizationMembers.clear();
  clearPlatformState();
}

function clearPlatformState() {
  externalResourceId.value = "";
  connections.value = [];
  platformHealth.value = null;
  moduleCatalog.clear();
  dashboardSummary.clear();
}

function clearConsoleState() {
  workspaceGeneration += 1;
  platform.value = "";
  platformAdapters.clear();
  organizationDirectory.clear();
  organizationMembers.clear();
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
    <header>
      <span class="eyebrow">MUXIVO</span>
      <h1>Console</h1>
      <p>One browser control plane for every Muxivo bot platform.</p>
    </header>

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
      <form @submit.prevent="signIn">
        <label>Email<input v-model="email" type="email" autocomplete="email" required /></label>
        <label>Password<input v-model="password" type="password" autocomplete="current-password" minlength="12" required /></label>
        <button :disabled="busy">{{ busy ? "Signing in…" : "Sign in" }}</button>
      </form>
    </section>

    <template v-else>
      <section class="card">
        <div class="section-heading">
          <div>
            <h2>Organizations</h2>
            <p>Choose the tenant whose platform resources you are allowed to manage.</p>
          </div>
          <button type="button" :disabled="busy" @click="signOut">{{ busy ? "Working…" : "Sign out" }}</button>
        </div>

        <div v-if="organizationState === 'loading'" class="directory-state" aria-live="polite">Loading your organizations…</div>
        <div v-else-if="organizationState === 'unavailable'" class="directory-state" role="alert">
          <p>Organization access could not be verified. Platform controls stay hidden.</p>
          <button type="button" :disabled="busy" @click="loadAuthenticatedConsole">Retry organizations</button>
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

        <form class="create-organization" @submit.prevent="createOrganization">
          <label>New organization name<input v-model="organizationName" maxlength="128" required /></label>
          <button :disabled="busy">{{ busy ? "Creating…" : "Create organization" }}</button>
        </form>

        <div v-if="platformAdapters.supports('discord', 'connection_registration')" class="identity-link">
          <h3>Discord identity</h3>
          <p>Link your Discord account before registering a Discord server connection. Discord remains the authority for server-native access.</p>
          <button type="button" :disabled="busy" @click="linkDiscord">Link Discord</button>
        </div>
      </section>

      <OrganizationMembersPanel
        v-if="organizationState === 'ready' && organizationId && canViewOrganizationMembers && selectedOrganizationRole"
        :state="organizationMembers.state.value"
        :members="organizationMembers.items.value"
        :actor-role="selectedOrganizationRole"
        :next-cursor="organizationMembers.nextCursor.value"
        :loading-more="organizationMembers.loadingMore.value"
        :updating-member-id="organizationMembers.updatingMemberId.value"
        :mutation-failed="organizationMembers.mutationFailed.value"
        @retry="reloadOrganizationMembers"
        @load-more="loadMoreOrganizationMembers"
        @change-role="changeOrganizationMemberRole"
      />

      <section v-if="organizationState === 'ready' && organizationId" class="card workspace">
        <div class="section-heading">
          <div>
            <h2>Control modules</h2>
            <p>Browser-ready capabilities are discovered through the Console BFF and each platform's versioned Control API.</p>
          </div>
          <span v-if="organizationDirectory.selected.value" class="role-badge">{{ organizationDirectory.selected.value.role }}</span>
        </div>
        <p v-if="moduleCatalog.state.value === 'loading'" class="directory-state">Loading authorized modules…</p>
        <p v-else-if="moduleCatalog.state.value === 'unavailable'" class="directory-state">Control modules are temporarily unavailable. No capability has been assumed.</p>
        <p v-else-if="moduleCatalog.state.value === 'empty'" class="directory-state">No browser-ready modules are exposed for this organization yet.</p>
        <ul v-else-if="moduleCatalog.state.value === 'ready'" class="module-grid">
          <li v-for="module in moduleCatalog.items.value" :key="module.key">
            <div>
              <span class="module-platform">{{ module.platform }}</span>
              <strong>{{ module.display_name }}</strong>
              <small>{{ module.key }}</small>
            </div>
            <div class="module-meta">
              <span>{{ module.capability }}</span>
              <em :data-status="module.status">{{ module.status.replaceAll("_", " ") }}</em>
            </div>
          </li>
        </ul>
        <DashboardSummaryPanel
          v-if="isControlModuleAvailable('discord.dashboard-summary')"
          :state="dashboardSummary.state.value"
          :summary="dashboardSummary.summary.value"
        />
      </section>

      <section v-if="organizationState === 'ready' && organizationId" class="card workspace">
        <div class="section-heading">
          <div>
            <h2>Platform connections</h2>
            <p>Connections belong to the selected organization. Platform services independently verify ownership and capability.</p>
          </div>
        </div>

        <p v-if="platformAdapters.state.value === 'loading'" class="directory-state">Loading configured connection adapters…</p>
        <p v-else-if="platformAdapters.state.value === 'unavailable'" class="directory-state">Connection adapters could not be verified. New connections are disabled.</p>
        <form v-else-if="connectionPlatforms.length" class="connection-form" @submit.prevent="registerConnection">
          <label>Platform
            <select v-model="platform" required>
              <option v-for="supportedPlatform in connectionPlatforms" :key="supportedPlatform" :value="supportedPlatform">
                {{ supportedPlatform }}
              </option>
            </select>
          </label>
          <label>External resource ID<input v-model="externalResourceId" required /></label>
          <button :disabled="busy || !platform">Register connection</button>
        </form>
        <p v-else class="directory-state">No platform adapter in this deployment currently supports new browser connections.</p>

        <ul v-if="connections.length" class="connections">
          <li v-for="connection in connections" :key="connection.id">
            <strong>{{ connection.platform }}</strong>
            <span>{{ connection.external_resource_id }}</span>
            <em :data-status="connection.status">{{ connection.status.replaceAll("_", " ") }}</em>
          </li>
        </ul>
        <p v-else class="empty-state">No platform connections are visible for this organization.</p>

        <section v-if="isControlModuleAvailable('discord.health')" class="platform-health" aria-labelledby="discord-health-heading">
          <div class="section-heading">
            <div>
              <h3 id="discord-health-heading">Discord platform health</h3>
              <p>Read-only runtime signals are requested through the Console BFF; Discord credentials never enter the browser.</p>
            </div>
            <button type="button" :disabled="busy" @click="loadDiscordHealth">{{ busy ? "Loading…" : "Load health" }}</button>
          </div>
          <ul v-if="platformHealth" class="health-signals">
            <li v-for="signal in platformHealth.signals" :key="signal.key">
              <span><strong>{{ signal.display_name }}</strong><small>{{ signal.value }}</small></span>
              <em :data-status="signal.status">{{ signal.status }}</em>
            </li>
          </ul>
        </section>
      </section>
    </template>

    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
  </main>
</template>