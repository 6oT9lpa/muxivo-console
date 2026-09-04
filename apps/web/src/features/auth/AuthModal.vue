<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "../../i18n";
import { clientLogger } from "../../utils/clientLogger";
import AuthField from "./AuthField.vue";

type AuthMode = "sign-in" | "create-account";
type AuthProvider = "discord" | "twitch" | "telegram" | "google" | "yandex";

const props = withDefaults(
  defineProps<{
    visible: boolean;
    busy: boolean;
    notice: string;
    invitationToken?: string;
    registrationVerificationSent?: boolean;
    registrationEmailVerified?: boolean;
    availableProviders?: AuthProvider[];
  }>(),
  {
    invitationToken: "",
    registrationVerificationSent: false,
    registrationEmailVerified: false,
    availableProviders: () => ["discord"],
  },
);

const authMode = defineModel<AuthMode>("authMode", { default: "sign-in" });
const email = defineModel<string>("email", { default: "" });
const password = defineModel<string>("password", { default: "" });
const registrationDisplayName = defineModel<string>("registrationDisplayName", { default: "" });
const registrationEmail = defineModel<string>("registrationEmail", { default: "" });
const registrationPassword = defineModel<string>("registrationPassword", { default: "" });
const recoveryEmail = defineModel<string>("recoveryEmail", { default: "" });
const recoveryToken = defineModel<string>("recoveryToken", { default: "" });
const recoveryNewPassword = defineModel<string>("recoveryNewPassword", { default: "" });
const recoveryConfirmPassword = defineModel<string>("recoveryConfirmPassword", { default: "" });
const registrationCode = defineModel<string>("registrationCode", { default: "" });

const emit = defineEmits<{
  (event: "close"): void;
  (event: "sign-in"): void;
  (event: "request-recovery"): void;
  (event: "complete-recovery"): void;
  (event: "request-registration-verification"): void;
  (event: "resend-registration-verification"): void;
  (event: "verify-registration"): void;
  (event: "reset-registration-verification"): void;
  (event: "continue-sign-in"): void;
  (event: "oauth-provider", provider: AuthProvider): void;
}>();

const { t } = useI18n();
const dialog = ref<HTMLElement | null>(null);
const forgotPasswordOpen = ref(Boolean(recoveryToken.value));
const fieldErrors = ref<Record<string, string>>({});
const providerNotice = ref("");
const previousBodyOverflow = ref("");
let initialFocusTimer: number | null = null;
const initialFocusDelayMs = 220;

const isSignIn = computed(() => authMode.value === "sign-in");
const registrationEmailLooksValid = computed(() =>
  /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(registrationEmail.value.trim()),
);
const registrationVerificationVisible = computed(
  () =>
    registrationEmailLooksValid.value ||
    props.registrationVerificationSent ||
    props.registrationEmailVerified,
);
const recoveryCompletionVisible = computed(() => Boolean(recoveryToken.value));
const providerDefinitions = computed(
  () =>
    [
      { id: "discord" as const, label: t("console.auth.provider_discord"), mark: "D" },
      { id: "twitch" as const, label: t("console.auth.provider_twitch"), mark: "T" },
      { id: "telegram" as const, label: t("console.auth.provider_telegram"), mark: "TG" },
      { id: "google" as const, label: t("console.auth.provider_google"), mark: "G" },
      { id: "yandex" as const, label: t("console.auth.provider_yandex"), mark: "Я" },
    ] satisfies Array<{ id: AuthProvider; label: string; mark: string }>,
);

function navLetters(label: string): string[] {
  return Array.from(label);
}

function clearErrors(): void {
  fieldErrors.value = {};
}

function validateEmail(value: string, key: string): boolean {
  if (!value.trim()) {
    fieldErrors.value[key] = t("console.auth.validation.email_required");
    return false;
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim())) {
    fieldErrors.value[key] = t("console.auth.validation.email_invalid");
    return false;
  }
  return true;
}

function validatePassword(value: string, key: string): boolean {
  if (!value) {
    fieldErrors.value[key] = t("console.auth.validation.password_required");
    return false;
  }
  if (value.length < 12) {
    fieldErrors.value[key] = t("console.auth.validation.password_short");
    return false;
  }
  return true;
}

function validateSignIn(): boolean {
  clearErrors();
  const validEmail = validateEmail(email.value, "signInEmail");
  const validPassword = validatePassword(password.value, "signInPassword");
  if (!validEmail || !validPassword) {
    clientLogger.info("console.auth.validation_failed", { mode: "sign-in" });
  }
  return validEmail && validPassword;
}

function validateRegistration(includeCode = false): boolean {
  clearErrors();
  let valid = true;
  if (!registrationDisplayName.value.trim()) {
    fieldErrors.value.registrationDisplayName = t("console.auth.validation.display_name_required");
    valid = false;
  } else if (registrationDisplayName.value.trim().length > 64) {
    fieldErrors.value.registrationDisplayName = t("console.auth.validation.display_name_long");
    valid = false;
  }
  valid = validateEmail(registrationEmail.value, "registrationEmail") && valid;
  valid = validatePassword(registrationPassword.value, "registrationPassword") && valid;
  if (includeCode && !/^\d{6}$/.test(registrationCode.value)) {
    fieldErrors.value.registrationCode = t("console.auth.validation.code_invalid");
    valid = false;
  }
  if (!valid) clientLogger.info("console.auth.validation_failed", { mode: "create-account" });
  return valid;
}

function submitSignIn(): void {
  if (validateSignIn()) emit("sign-in");
}

function submitRegistration(): void {
  if (props.registrationEmailVerified) {
    emit("continue-sign-in");
    return;
  }
  if (!validateRegistration()) return;
  emit("request-registration-verification");
}

function requestRegistrationVerification(): void {
  if (validateRegistration()) emit("request-registration-verification");
}

function resendRegistrationVerification(): void {
  if (validateRegistration()) emit("resend-registration-verification");
}

function verifyRegistration(): void {
  if (validateRegistration(true)) emit("verify-registration");
}

function submitRecoveryRequest(): void {
  clearErrors();
  if (validateEmail(recoveryEmail.value, "recoveryEmail")) emit("request-recovery");
}

function submitRecoveryCompletion(): void {
  clearErrors();
  let valid = Boolean(recoveryToken.value.trim());
  if (!valid) fieldErrors.value.recoveryToken = t("console.auth.validation.token_required");
  valid = validatePassword(recoveryNewPassword.value, "recoveryNewPassword") && valid;
  if (recoveryNewPassword.value !== recoveryConfirmPassword.value) {
    fieldErrors.value.recoveryConfirmPassword = t("console.auth.validation.password_mismatch");
    valid = false;
  }
  if (valid) emit("complete-recovery");
}

function openRecovery(): void {
  forgotPasswordOpen.value = true;
  providerNotice.value = "";
  clientLogger.info("console.auth.recovery_opened");
}

function handleProvider(provider: AuthProvider): void {
  if (!props.availableProviders.includes(provider)) {
    providerNotice.value = t("console.auth.provider_unavailable");
    clientLogger.info("console.auth.provider_unavailable", { provider });
    return;
  }
  providerNotice.value = "";
  emit("oauth-provider", provider);
}

function handleDialogKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") {
    event.preventDefault();
    emit("close");
    return;
  }
  if (event.key !== "Tab") return;
  const root = dialog.value;
  if (!root) return;
  const focusable = Array.from(
    root.querySelectorAll<HTMLElement>(
      "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex='-1'])",
    ),
  ).filter((element) => element.getClientRects().length > 0);
  if (!focusable.length) {
    event.preventDefault();
    return;
  }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

async function focusInitialControl(): Promise<void> {
  await nextTick();
  const recoveryInput = forgotPasswordOpen.value
    ? dialog.value?.querySelector<HTMLElement>(
        ".auth-recovery-flow input:not([disabled])",
      )
    : null;
  const first =
    recoveryInput ??
    dialog.value?.querySelector<HTMLElement>("input:not([disabled])") ??
    dialog.value?.querySelector<HTMLElement>("button:not([disabled])");
  first?.focus({ preventScroll: true });
}

function scheduleInitialFocus(delay = initialFocusDelayMs): void {
  if (initialFocusTimer !== null && typeof window !== "undefined") {
    window.clearTimeout(initialFocusTimer);
  }
  if (typeof window === "undefined") {
    void focusInitialControl();
    return;
  }
  initialFocusTimer = window.setTimeout(() => {
    initialFocusTimer = null;
    void focusInitialControl();
  }, delay);
}

watch(
  () => authMode.value,
  () => {
    clearErrors();
    providerNotice.value = "";
    scheduleInitialFocus();
  },
);

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return;
    scheduleInitialFocus();
  },
);

watch(
  () => forgotPasswordOpen.value,
  () => {
    scheduleInitialFocus();
  },
);

watch(registrationEmail, (value, previous) => {
  if (previous && value !== previous && props.registrationVerificationSent) {
    registrationCode.value = "";
    emit("reset-registration-verification");
  }
});

onMounted(() => {
  if (typeof document !== "undefined") {
    previousBodyOverflow.value = document.body.style.overflow;
    document.body.style.overflow = "hidden";
  }
  clientLogger.info("console.auth.modal_mounted");
});

onBeforeUnmount(() => {
  if (initialFocusTimer !== null && typeof window !== "undefined") {
    window.clearTimeout(initialFocusTimer);
  }
  if (typeof document !== "undefined") document.body.style.overflow = previousBodyOverflow.value;
  clientLogger.info("console.auth.modal_unmounted");
});
</script>

<template>
  <section
    ref="dialog"
    class="login-overlay"
    :class="{ 'is-visible': visible }"
    role="dialog"
    aria-modal="true"
    aria-labelledby="console-auth-dialog-title"
    @click.self="emit('close')"
    @keydown="handleDialogKeydown"
  >
    <div class="auth-shader" aria-hidden="true"></div>
    <div class="login-panel" @click.stop>
      <button
        class="close-login"
        type="button"
        :aria-label="t('console.auth.close')"
        @click="emit('close')"
      >
        <span aria-hidden="true">×</span>
      </button>

      <div class="auth-panel-heading">
        <span class="eyebrow">{{ t("console.auth.eyebrow") }}</span>
        <h2 id="console-auth-dialog-title">
          {{ isSignIn ? t("console.auth.welcome_title") : t("console.auth.create_title") }}
        </h2>
        <p>
          {{ isSignIn ? t("console.auth.sign_in_description") : t("console.auth.create_description") }}
        </p>
      </div>

      <div v-if="invitationToken" class="auth-invitation-context" role="status">
        <strong>{{ t("console.invitation.accept_title") }}</strong>
        <p>{{ t("console.invitation.accept_description") }}</p>
      </div>

      <div class="auth-mode-tabs" role="tablist" :aria-label="t('console.auth.mode_label')">
        <button
          class="animated-nav-link public-nav-button auth-mode-tab"
          type="button"
          role="tab"
          :aria-label="t('console.auth.sign_in')"
          :aria-selected="isSignIn"
          :class="{ active: isSignIn }"
          @click="authMode = 'sign-in'"
        >
          <span
            v-for="(letter, index) in navLetters(t('console.auth.sign_in'))"
            :key="`sign-in-${letter}-${index}`"
            class="animated-nav-link-letter"
            :style="{ transitionDelay: `${index * 22}ms` }"
          >{{ letter === " " ? "\u00a0" : letter }}</span>
        </button>
        <button
          class="animated-nav-link public-nav-button auth-mode-tab"
          type="button"
          role="tab"
          :aria-label="t('console.auth.create_account')"
          :aria-selected="!isSignIn"
          :class="{ active: !isSignIn }"
          @click="authMode = 'create-account'"
        >
          <span
            v-for="(letter, index) in navLetters(t('console.auth.create_account'))"
            :key="`create-${letter}-${index}`"
            class="animated-nav-link-letter"
            :style="{ transitionDelay: `${index * 22}ms` }"
          >{{ letter === " " ? "\u00a0" : letter }}</span>
        </button>
      </div>

      <Transition name="auth-content" mode="out-in">
        <form v-if="isSignIn" key="sign-in" class="auth-form" novalidate @submit.prevent="submitSignIn">
          <AuthField
            id="console-auth-email"
            v-model="email"
            :label="t('console.auth.email')"
            type="email"
            autocomplete="email"
            inputmode="email"
            required
            :error="fieldErrors.signInEmail"
          />
          <AuthField
            id="console-auth-password"
            v-model="password"
            :label="t('console.auth.password')"
            type="password"
            autocomplete="current-password"
            :minlength="12"
            required
            :error="fieldErrors.signInPassword"
          />
          <button class="auth-submit" type="submit" :disabled="busy">
            <span v-if="busy" class="auth-spinner" aria-hidden="true"></span>
            {{ busy ? t("console.auth.signing_in") : t("console.auth.sign_in_button") }}
          </button>
          <button class="auth-inline-link auth-forgot-link" type="button" @click="openRecovery">
            {{ t("console.auth.forgot_password") }}
          </button>
        </form>

        <form v-else key="create-account" class="auth-form" novalidate @submit.prevent="submitRegistration">
          <AuthField
            id="console-auth-display-name"
            v-model="registrationDisplayName"
            :label="t('console.auth.display_name')"
            autocomplete="name"
            :maxlength="64"
            required
            :error="fieldErrors.registrationDisplayName"
          />
          <AuthField
            id="console-auth-registration-email"
            v-model="registrationEmail"
            :label="t('console.auth.email')"
            type="email"
            autocomplete="email"
            inputmode="email"
            required
            :error="fieldErrors.registrationEmail"
          />
          <AuthField
            id="console-auth-registration-password"
            v-model="registrationPassword"
            :label="t('console.auth.password')"
            type="password"
            autocomplete="new-password"
            :minlength="12"
            :maxlength="1024"
            required
            :error="fieldErrors.registrationPassword"
          />

          <Transition name="auth-subflow">
            <section v-if="registrationVerificationVisible" class="auth-verification-block" aria-live="polite">
              <div class="auth-subflow-heading">
                <span class="auth-step-indicator">02</span>
                <div>
                  <h3>{{ t("console.auth.verification_heading") }}</h3>
                  <p>{{ t("console.auth.verification_description") }}</p>
                </div>
              </div>
              <AuthField
                id="console-auth-registration-code"
                v-model="registrationCode"
                :label="t('console.auth.verification_code')"
                autocomplete="one-time-code"
                inputmode="numeric"
                :maxlength="6"
                :minlength="6"
                :disabled="registrationEmailVerified"
                :error="fieldErrors.registrationCode"
                :hint="registrationEmailVerified ? t('console.auth.email_verified') : ''"
                :action-label="registrationVerificationSent ? t('console.auth.resend_code') : t('console.auth.send_code')"
                :action-busy-label="t('console.auth.sending_code')"
                :action-busy="busy"
                :action-disabled="registrationEmailVerified || !registrationEmailLooksValid"
                @action="registrationVerificationSent ? resendRegistrationVerification() : requestRegistrationVerification()"
              />
              <p v-if="registrationEmailVerified" class="auth-success-message" role="status">
                <span aria-hidden="true">✓</span> {{ t("console.auth.email_verified") }}
              </p>
              <button
                v-else
                class="auth-secondary-submit"
                type="button"
                :disabled="busy || !registrationVerificationSent"
                @click="verifyRegistration"
              >
                <span v-if="busy" class="auth-spinner" aria-hidden="true"></span>
                {{ busy ? t("console.auth.verifying_code") : t("console.auth.verify_code") }}
              </button>
            </section>
          </Transition>

          <button class="auth-submit" type="submit" :disabled="busy">
            <span v-if="busy" class="auth-spinner" aria-hidden="true"></span>
            {{
              busy
                ? t("console.auth.creating")
                : registrationEmailVerified
                  ? t("console.auth.continue_sign_in")
                  : t("console.auth.create_button")
            }}
          </button>
        </form>
      </Transition>

      <Transition name="auth-notice">
        <p v-if="notice" class="auth-notice" role="status">{{ notice }}</p>
      </Transition>

      <Transition name="auth-subflow">
        <section v-if="forgotPasswordOpen" class="auth-subflow auth-recovery-flow">
          <div class="auth-subflow-heading">
            <span class="auth-step-indicator">↗</span>
            <div>
              <h3>{{ t("console.auth.recovery_heading") }}</h3>
              <p>{{ t("console.auth.recovery_description") }}</p>
            </div>
          </div>
          <form v-if="!recoveryCompletionVisible" class="auth-form" novalidate @submit.prevent="submitRecoveryRequest">
            <AuthField
              id="console-auth-recovery-email"
              v-model="recoveryEmail"
              :label="t('console.auth.account_email')"
              type="email"
              autocomplete="email"
              inputmode="email"
              :placeholder="t('console.auth.email_placeholder')"
              required
              :error="fieldErrors.recoveryEmail"
            />
            <button class="auth-secondary-submit" type="submit" :disabled="busy">
              <span v-if="busy" class="auth-spinner" aria-hidden="true"></span>
              {{ busy ? t("console.auth.requesting") : t("console.auth.request_reset") }}
            </button>
          </form>
          <form v-else class="auth-form" novalidate @submit.prevent="submitRecoveryCompletion">
            <AuthField
              id="console-auth-recovery-token"
              v-model="recoveryToken"
              :label="t('console.auth.recovery_token')"
              autocomplete="one-time-code"
              :error="fieldErrors.recoveryToken"
            />
            <AuthField
              id="console-auth-recovery-new-password"
              v-model="recoveryNewPassword"
              :label="t('console.auth.new_password')"
              type="password"
              autocomplete="new-password"
              :minlength="12"
              :maxlength="1024"
              :error="fieldErrors.recoveryNewPassword"
            />
            <AuthField
              id="console-auth-recovery-confirm-password"
              v-model="recoveryConfirmPassword"
              :label="t('console.auth.confirm_password')"
              type="password"
              autocomplete="new-password"
              :minlength="12"
              :maxlength="1024"
              :error="fieldErrors.recoveryConfirmPassword"
            />
            <button class="auth-secondary-submit" type="submit" :disabled="busy">
              <span v-if="busy" class="auth-spinner" aria-hidden="true"></span>
              {{ busy ? t("console.auth.resetting") : t("console.auth.reset_password") }}
            </button>
          </form>
          <button class="auth-inline-link auth-back-link" type="button" @click="forgotPasswordOpen = false">
            {{ t("console.auth.back_to_sign_in") }}
          </button>
        </section>
      </Transition>

      <section class="auth-providers" aria-labelledby="auth-providers-heading">
        <div class="auth-or"><span>{{ t("console.auth.or") }}</span></div>
        <h3 id="auth-providers-heading">{{ t("console.auth.providers_heading") }}</h3>
        <p>{{ t("console.auth.providers_description") }}</p>
        <div class="auth-provider-grid">
          <button
            v-for="provider in providerDefinitions"
            :key="provider.id"
            class="auth-provider-button"
            :class="{ 'is-available': availableProviders.includes(provider.id) }"
            type="button"
            :disabled="busy || !availableProviders.includes(provider.id)"
            :aria-label="provider.label"
            :title="availableProviders.includes(provider.id) ? provider.label : t('console.auth.provider_soon')"
            @click="handleProvider(provider.id)"
          >
            <span class="auth-provider-mark" aria-hidden="true">{{ provider.mark }}</span>
            <span>{{ provider.label }}</span>
            <small v-if="!availableProviders.includes(provider.id)">{{ t("console.auth.provider_soon") }}</small>
          </button>
        </div>
        <p v-if="providerNotice" class="auth-provider-notice" role="status">{{ providerNotice }}</p>
      </section>
    </div>
  </section>
</template>
