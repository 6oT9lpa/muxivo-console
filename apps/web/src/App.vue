<script setup lang="ts">
import { ref } from "vue";
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

type Organization = { id: string; name: string; slug: string };
type PlatformConnection = {
  id: string;
  organization_id: string;
  platform: "discord" | "twitch" | "telegram";
  external_resource_id: string;
  status: "pending" | "active" | "degraded" | "reauth_required" | "disconnected";
};

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
  } catch (error) {
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
    </section>
    <section v-if="authenticated" class="card workspace">
      <h2>Platform connections</h2>
      <p>Choose an organization, then connect a platform resource. The platform service independently verifies the request.</p>
      <form @submit.prevent="loadConnections"><label>Organization ID<input v-model="organizationId" inputmode="text" placeholder="UUID" required /></label><button :disabled="busy">{{ busy ? "Loading…" : "Load connections" }}</button></form>
      <form v-if="organizationId" class="connection-form" @submit.prevent="registerConnection"><label>Platform<select v-model="platform"><option value="discord">Discord</option><option value="twitch">Twitch</option><option value="telegram">Telegram</option></select></label><label>External resource ID<input v-model="externalResourceId" required /></label><button :disabled="busy">Register connection</button></form>
      <ul v-if="connections.length" class="connections"><li v-for="connection in connections" :key="connection.id"><strong>{{ connection.platform }}</strong><span>{{ connection.external_resource_id }}</span><em :data-status="connection.status">{{ connection.status.replaceAll("_", " ") }}</em></li></ul>
    </section>
    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
  </main>
</template>
