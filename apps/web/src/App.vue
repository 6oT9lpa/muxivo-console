<script setup lang="ts">
import { ref } from "vue";
import { consoleApi, ConsoleApiError } from "./api/consoleApi";

const email = ref("");
const password = ref("");
const organizationName = ref("");
const authenticated = ref(false);
const busy = ref(false);
const notice = ref("");

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
    const organization = await consoleApi<{ name: string; slug: string }>("/api/v1/organizations", {
      method: "POST",
      body: JSON.stringify({ name: organizationName.value }),
    });
    organizationName.value = "";
    notice.value = `Organization ${organization.name} is ready (${organization.slug}).`;
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
    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
  </main>
</template>
