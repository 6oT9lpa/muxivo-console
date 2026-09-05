<script setup lang="ts">
import { computed } from "vue";

import { useI18n } from "../../i18n";
import { formatSecurityTimestamp } from "../../utils/securityPresentation";
import type { BrowserSession, LoginIdentity } from "./types";

const { t } = useI18n();

const props = defineProps<{
  busy: boolean;
  browserSessions: BrowserSession[];
  loginIdentities: LoginIdentity[];
  canRevokeAllBrowserSessions: boolean;
  reauthenticationPassword: string;
  currentPassword: string;
  newPassword: string;
  confirmNewPassword: string;
}>();

const emit = defineEmits<{
  (event: "refresh-security"): void;
  (event: "refresh-recent-authentication"): void;
  (event: "refresh-identities"): void;
  (event: "unlink-identity", identity: LoginIdentity): void;
  (event: "change-password"): void;
  (event: "revoke-current-session"): void;
  (event: "revoke-all-sessions"): void;
  (event: "update:reauthenticationPassword", value: string): void;
  (event: "update:currentPassword", value: string): void;
  (event: "update:newPassword", value: string): void;
  (event: "update:confirmNewPassword", value: string): void;
}>();

const reauthenticationPasswordModel = computed({
  get: () => props.reauthenticationPassword,
  set: (value: string) => emit("update:reauthenticationPassword", value),
});

const currentPasswordModel = computed({
  get: () => props.currentPassword,
  set: (value: string) => emit("update:currentPassword", value),
});

const newPasswordModel = computed({
  get: () => props.newPassword,
  set: (value: string) => emit("update:newPassword", value),
});

const confirmNewPasswordModel = computed({
  get: () => props.confirmNewPassword,
  set: (value: string) => emit("update:confirmNewPassword", value),
});

function formatSessionTime(value: string | null): string {
  return formatSecurityTimestamp(value);
}

function providerLabel(provider: LoginIdentity["provider"]): string {
  return provider === "email"
    ? t("console.security.email_password")
    : t(`console.identity_provider.${provider}`);
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
  return props.canRevokeAllBrowserSessions
    ? t("console.security.bulk_ready")
    : t("console.security.bulk_requires_recent_auth");
}
</script>

<template>
  <section id="console-security" class="card workspace console-section">
    <div class="section-heading">
      <div>
        <h2>{{ t("console.security.title") }}</h2>
        <p>{{ t("console.security.description") }}</p>
      </div>
      <button type="button" :disabled="busy" @click="emit('refresh-security')">
        {{ busy ? t("console.security.refreshing") : t("console.security.refresh") }}
      </button>
    </div>

    <ul v-if="browserSessions.length" class="health-signals audit-events">
      <li v-for="session in browserSessions" :key="session.id">
        <span>
          <strong>
            {{ session.device_label }}{{ session.is_current ? ` · ${t("console.security.session_current")}` : "" }}
          </strong>
          <small>
            {{ t("console.security.last_seen", { value: formatSessionTime(session.last_seen_at) }) }} ·
            {{ t("console.security.expires", { value: formatSessionTime(session.expires_at) }) }}
          </small>
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

    <form class="connection-form" @submit.prevent="emit('refresh-recent-authentication')">
      <label>
        {{ t("console.security.recent_auth_label") }}
        <input
          v-model="reauthenticationPasswordModel"
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
      <button type="button" :disabled="busy" @click="emit('refresh-identities')">
        {{ t("console.security.refresh_identities") }}
      </button>
    </div>

    <ul v-if="loginIdentities.length" class="health-signals audit-events">
      <li v-for="identity in loginIdentities" :key="identity.id">
        <span>
          <strong>{{ providerLabel(identity.provider) }}</strong>
          <small>
            {{ t("console.security.linked", { value: formatSessionTime(identity.linked_at) }) }} ·
            {{ t("console.security.last_used", { value: formatSessionTime(identity.last_used_at) }) }}
          </small>
          <small>{{ identityProtectionLabel(identity) }}</small>
        </span>
        <button
          type="button"
          :disabled="busy || !identity.can_unlink"
          @click="emit('unlink-identity', identity)"
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

    <form class="connection-form" @submit.prevent="emit('change-password')">
      <label>
        {{ t("console.security.current_password_placeholder") }}
        <input
          v-model="currentPasswordModel"
          type="password"
          autocomplete="current-password"
          required
        />
      </label>
      <label>
        {{ t("console.auth.new_password") }}
        <input
          v-model="newPasswordModel"
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
          v-model="confirmNewPasswordModel"
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
      <button type="button" :disabled="busy" @click="emit('revoke-current-session')">
        {{ t("console.security.revoke_current") }}
      </button>
      <button
        type="button"
        :disabled="busy || !canRevokeAllBrowserSessions"
        @click="emit('revoke-all-sessions')"
      >
        {{ t("console.security.revoke_all") }}
      </button>
      <p>{{ sessionBulkRevocationLabel() }}</p>
    </div>
  </section>
</template>
