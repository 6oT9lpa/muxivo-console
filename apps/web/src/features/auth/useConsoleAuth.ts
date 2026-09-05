import { ref, type Ref } from "vue";

import { consoleApi, ConsoleApiError } from "../../api/consoleApi";
import { clientLogger } from "../../utils/clientLogger";
import {
  passwordChangeValidationMessage,
  passwordRecoveryCompletionValidationMessage,
} from "../../utils/passwordChange";
import { accountRegistrationValidationMessage } from "../../utils/accountRegistration";
import type { TranslationParams } from "../../i18n";
import type { BrowserSession, LoginIdentity } from "../console/types";

export type AuthProvider = "discord" | "twitch" | "telegram" | "google" | "yandex";

type Translate = (key: string, params?: TranslationParams) => string;

type ConsoleAuthDependencies = {
  t: Translate;
  busy: Ref<boolean>;
  notice: Ref<string>;
  authenticated: Ref<boolean>;
  closeLoginModal: () => void;
  loadOrganizations: (preferredOrganizationId?: string) => Promise<void>;
  acceptInvitationIfPresent: () => Promise<void>;
};

const AUTH_PROVIDERS = new Set<AuthProvider>([
  "discord",
  "twitch",
  "telegram",
  "google",
  "yandex",
]);

/** Owns authentication state and transport orchestration for the public shell. */
export function useConsoleAuth(dependencies: ConsoleAuthDependencies) {
  const {
    t,
    busy,
    notice,
    authenticated,
    closeLoginModal,
    loadOrganizations,
    acceptInvitationIfPresent,
  } = dependencies;

  const authMode = ref<"sign-in" | "create-account">("sign-in");
  const email = ref("");
  const password = ref("");
  const registrationDisplayName = ref("");
  const registrationEmail = ref("");
  const registrationPassword = ref("");
  const currentPassword = ref("");
  const reauthenticationPassword = ref("");
  const newPassword = ref("");
  const confirmNewPassword = ref("");
  const recoveryEmail = ref("");
  const recoveryNewPassword = ref("");
  const recoveryConfirmPassword = ref("");
  const registrationCode = ref("");
  const registrationVerificationToken = ref("");
  const registrationVerificationSent = ref(false);
  const registrationEmailVerified = ref(false);
  const availableAuthProviders = ref<AuthProvider[]>([]);
  const browserSessions = ref<BrowserSession[]>([]);
  const loginIdentities = ref<LoginIdentity[]>([]);

  const initialAuthUrl =
    typeof window !== "undefined" ? new URL(window.location.href) : null;
  const recoveryToken = ref(
    initialAuthUrl?.searchParams.get("recovery_token") ??
      (isPasswordRecoveryPath(initialAuthUrl)
        ? initialAuthUrl?.searchParams.get("token") ?? ""
        : ""),
  );
  const invitationToken = ref(
    initialAuthUrl && !isPasswordRecoveryPath(initialAuthUrl)
      ? initialAuthUrl.searchParams.get("token") ?? ""
      : "",
  );
  const identityLinkedProvider = ref<AuthProvider | null>(
    isAuthProvider(initialAuthUrl?.searchParams.get("identity_linked") ?? "")
      ? (initialAuthUrl?.searchParams.get("identity_linked") as AuthProvider)
      : null,
  );

  async function signIn(): Promise<void> {
    busy.value = true;
    notice.value = "";
    clientLogger.info("console.auth.sign_in.requested");
    try {
      await consoleApi<void>("/api/v1/auth/email-password/sessions", {
        method: "POST",
        body: JSON.stringify({ email: email.value, password: password.value }),
      });
      authenticated.value = true;
      closeLoginModal();
      password.value = "";
      notice.value = t("console.notice.signed_in");
      await Promise.all([loadOrganizations(), loadBrowserSessions(), loadLoginIdentities()]);
      await acceptInvitationIfPresent();
      clientLogger.info("console.auth.sign_in.succeeded");
    } catch (error) {
      notice.value = messageFor(error);
      clientLogger.warn("console.auth.sign_in.failed", {
        error_type: error instanceof Error ? error.name : "unknown",
      });
    } finally {
      busy.value = false;
    }
  }

  async function requestRegistrationVerification(): Promise<void> {
    const validationMessage = accountRegistrationValidationMessage({
      displayName: registrationDisplayName.value,
      email: registrationEmail.value,
      password: registrationPassword.value,
    });
    if (validationMessage) {
      notice.value = validationMessage;
      return;
    }
    busy.value = true;
    notice.value = "";
    clientLogger.info("console.auth.recovery.requested");
    try {
      const response = await consoleApi<{
        status: "verification_required";
        verification_token?: string;
      }>("/api/v1/auth/email-password/registrations", {
        method: "POST",
        body: JSON.stringify({
          email: registrationEmail.value,
          password: registrationPassword.value,
          display_name: registrationDisplayName.value,
        }),
      });
      registrationVerificationToken.value = response.verification_token ?? "";
      registrationVerificationSent.value = Boolean(response.verification_token);
      registrationEmailVerified.value = false;
      registrationCode.value = "";
      notice.value = t("console.notice.verification_requested");
      clientLogger.info("console.auth.registration.verification_requested");
    } catch (error) {
      notice.value = messageFor(error);
    } finally {
      busy.value = false;
    }
  }

  async function resendRegistrationVerification(): Promise<void> {
    if (!registrationVerificationToken.value) {
      await requestRegistrationVerification();
      return;
    }
    busy.value = true;
    notice.value = "";
    try {
      const response = await consoleApi<{
        status: "verification_required";
        verification_token: string;
      }>("/api/v1/auth/email-password/registration-verifications/resend", {
        method: "POST",
        body: JSON.stringify({ token: registrationVerificationToken.value }),
      });
      if (response.verification_token) {
        registrationVerificationToken.value = response.verification_token;
      }
      registrationVerificationSent.value = true;
      notice.value = t("console.notice.verification_requested");
      clientLogger.info("console.auth.registration.verification_resent");
    } catch (error) {
      registrationVerificationToken.value = "";
      registrationVerificationSent.value = false;
      registrationCode.value = "";
      notice.value = messageFor(error);
    } finally {
      busy.value = false;
    }
  }

  async function verifyRegistration(): Promise<void> {
    if (!registrationVerificationToken.value) return;
    busy.value = true;
    notice.value = "";
    try {
      await consoleApi<{ status: "verified" }>(
        "/api/v1/auth/email-password/registration-verifications",
        {
          method: "POST",
          body: JSON.stringify({
            token: registrationVerificationToken.value,
            code: registrationCode.value,
          }),
        },
      );
      email.value = registrationEmail.value;
      registrationEmailVerified.value = true;
      registrationVerificationSent.value = true;
      registrationVerificationToken.value = "";
      registrationPassword.value = "";
      notice.value = t("console.notice.email_verified");
      clientLogger.info("console.auth.registration.verification_completed");
    } catch (error) {
      notice.value = messageFor(error);
    } finally {
      busy.value = false;
    }
  }

  function resetRegistrationVerification(): void {
    registrationVerificationToken.value = "";
    registrationVerificationSent.value = false;
    registrationEmailVerified.value = false;
    registrationCode.value = "";
    clientLogger.info("console.auth.registration.verification_reset");
  }

  function continueToSignIn(): void {
    authMode.value = "sign-in";
    password.value = "";
    notice.value = t("console.notice.account_created");
  }

  async function loadAuthProviders(): Promise<void> {
    try {
      const payload = await consoleApi<{ providers: string[] }>("/api/v1/auth/providers");
      availableAuthProviders.value = payload.providers.filter(isAuthProvider);
      clientLogger.info("console.auth.providers_loaded", {
        providers: availableAuthProviders.value.join(","),
      });
    } catch (error) {
      availableAuthProviders.value = [];
      clientLogger.info("console.auth.providers_unavailable", {
        error: error instanceof Error ? error.name : "unknown",
      });
    }
  }

  async function signInWithProvider(provider: AuthProvider): Promise<void> {
    const authorizationPaths: Partial<Record<AuthProvider, string>> = {
      discord: "/api/v1/auth/discord/authorizations",
      twitch: "/api/v1/auth/twitch/authorizations",
      telegram: "/api/v1/auth/telegram/authorizations",
      google: "/api/v1/auth/google/authorizations",
      yandex: "/api/v1/auth/yandex/authorizations",
    };
    const authorizationPath = authorizationPaths[provider];
    if (!authorizationPath) {
      notice.value = t("console.auth.provider_unavailable");
      clientLogger.info("console.auth.provider_unavailable", { provider });
      return;
    }
    busy.value = true;
    notice.value = "";
    try {
      const authorization = await consoleApi<{ authorization_url: string }>(
        authorizationPath,
        { method: "POST" },
      );
      window.location.assign(authorization.authorization_url);
    } catch (error) {
      notice.value = messageFor(error);
      busy.value = false;
    }
  }

  async function requestPasswordRecovery(): Promise<void> {
    busy.value = true;
    notice.value = "";
    try {
      await consoleApi<{ status: "accepted" }>("/api/v1/auth/password-recovery/requests", {
        method: "POST",
        body: JSON.stringify({ email: recoveryEmail.value || email.value }),
      });
      notice.value = t("console.notice.recovery_requested");
      clientLogger.info("console.auth.recovery.accepted");
    } catch (error) {
      notice.value = messageFor(error);
      clientLogger.warn("console.auth.recovery.failed", {
        error_type: error instanceof Error ? error.name : "unknown",
      });
    } finally {
      busy.value = false;
    }
  }

  async function completePasswordRecovery(): Promise<void> {
    const validationMessage = passwordRecoveryCompletionValidationMessage({
      token: recoveryToken.value,
      newPassword: recoveryNewPassword.value,
      confirmNewPassword: recoveryConfirmPassword.value,
    });
    if (validationMessage) {
      notice.value = validationMessage;
      return;
    }
    busy.value = true;
    notice.value = "";
    clientLogger.info("console.auth.recovery.completion_requested");
    try {
      await consoleApi<void>("/api/v1/auth/password-recovery/completions", {
        method: "POST",
        body: JSON.stringify({
          token: recoveryToken.value,
          new_password: recoveryNewPassword.value,
        }),
      });
      recoveryToken.value = "";
      recoveryNewPassword.value = "";
      recoveryConfirmPassword.value = "";
      password.value = "";
      notice.value = t("console.notice.password_reset");
      clientLogger.info("console.auth.recovery.completed");
    } catch (error) {
      notice.value =
        error instanceof ConsoleApiError && error.status === 403
          ? t("console.notice.recovery_invalid")
          : messageFor(error);
      clientLogger.warn("console.auth.recovery.completion_failed", {
        error_type: error instanceof Error ? error.name : "unknown",
      });
    } finally {
      busy.value = false;
    }
  }

  async function linkExternalIdentity(provider: AuthProvider): Promise<void> {
    busy.value = true;
    notice.value = "";
    clientLogger.info("console.auth.identity_link.requested", { provider });
    try {
      const authorization = await consoleApi<{ authorization_url: string }>(
        `/api/v1/identity-links/${provider}/authorizations`,
        { method: "POST" },
      );
      window.location.assign(authorization.authorization_url);
    } catch (error) {
      notice.value = messageFor(error);
      clientLogger.warn("console.auth.identity_link.failed", {
        provider,
        error_type: error instanceof Error ? error.name : "unknown",
      });
      busy.value = false;
    }
  }

  async function loadBrowserSessions(): Promise<void> {
    if (!authenticated.value) return;
    busy.value = true;
    notice.value = "";
    try {
      const payload = await consoleApi<{ items: BrowserSession[] }>("/api/v1/auth/sessions");
      browserSessions.value = payload.items;
      clientLogger.info("console.security.sessions.loaded", { count: payload.items.length });
    } catch (error) {
      browserSessions.value = [];
      notice.value = messageFor(error);
      clientLogger.warn("console.security.sessions.load_failed", {
        error_type: error instanceof Error ? error.name : "unknown",
      });
    } finally {
      busy.value = false;
    }
  }

  async function refreshSecurity(): Promise<void> {
    await Promise.all([loadBrowserSessions(), loadLoginIdentities()]);
  }

  async function loadLoginIdentities(): Promise<void> {
    if (!authenticated.value) return;
    busy.value = true;
    notice.value = "";
    try {
      const payload = await consoleApi<{ items: LoginIdentity[] }>("/api/v1/auth/identities");
      loginIdentities.value = payload.items;
      clientLogger.info("console.security.identities.loaded", { count: payload.items.length });
    } catch (error) {
      loginIdentities.value = [];
      notice.value = messageFor(error);
      clientLogger.warn("console.security.identities.load_failed", {
        error_type: error instanceof Error ? error.name : "unknown",
      });
    } finally {
      busy.value = false;
    }
  }

  async function unlinkLoginIdentity(identity: LoginIdentity): Promise<void> {
    busy.value = true;
    notice.value = "";
    clientLogger.info("console.security.identity_unlink.requested", {
      provider: identity.provider,
    });
    try {
      await consoleApi<LoginIdentity>(
        `/api/v1/auth/identities/${encodeURIComponent(identity.id)}`,
        { method: "DELETE" },
      );
      loginIdentities.value = loginIdentities.value.filter((item) => item.id !== identity.id);
      notice.value = t("console.notice.identity_unlinked", {
        provider: providerLabel(identity.provider),
      });
      clientLogger.info("console.security.identity_unlink.completed", {
        provider: identity.provider,
      });
    } catch (error) {
      notice.value = messageFor(error);
      clientLogger.warn("console.security.identity_unlink.failed", {
        provider: identity.provider,
        error_type: error instanceof Error ? error.name : "unknown",
      });
    } finally {
      busy.value = false;
    }
  }

  async function changePassword(): Promise<void> {
    const validationMessage = passwordChangeValidationMessage({
      currentPassword: currentPassword.value,
      newPassword: newPassword.value,
      confirmNewPassword: confirmNewPassword.value,
    });
    if (validationMessage) {
      notice.value = validationMessage;
      return;
    }
    busy.value = true;
    notice.value = "";
    clientLogger.info("console.security.password_change.requested");
    try {
      await consoleApi<void>("/api/v1/auth/password", {
        method: "PUT",
        body: JSON.stringify({
          current_password: currentPassword.value,
          new_password: newPassword.value,
        }),
      });
      currentPassword.value = "";
      newPassword.value = "";
      confirmNewPassword.value = "";
      notice.value = t("console.notice.password_changed");
      await loadBrowserSessions();
      clientLogger.info("console.security.password_change.completed");
    } catch (error) {
      notice.value = messageFor(error);
      clientLogger.warn("console.security.password_change.failed", {
        error_type: error instanceof Error ? error.name : "unknown",
      });
    } finally {
      busy.value = false;
    }
  }

  async function refreshRecentAuthentication(): Promise<void> {
    if (!reauthenticationPassword.value) {
      notice.value = t("console.notice.enter_password");
      return;
    }
    busy.value = true;
    notice.value = "";
    clientLogger.info("console.security.reauthentication.requested");
    try {
      await consoleApi<void>("/api/v1/auth/session/reauthentications", {
        method: "POST",
        body: JSON.stringify({ current_password: reauthenticationPassword.value }),
      });
      reauthenticationPassword.value = "";
      notice.value = t("console.notice.recent_auth_refreshed");
      await loadBrowserSessions();
      clientLogger.info("console.security.reauthentication.completed");
    } catch (error) {
      notice.value = messageFor(error);
      clientLogger.warn("console.security.reauthentication.failed", {
        error_type: error instanceof Error ? error.name : "unknown",
      });
    } finally {
      busy.value = false;
    }
  }

  function clearInvitationToken(): void {
    invitationToken.value = "";
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    url.searchParams.delete("token");
    window.history.replaceState(
      window.history.state,
      document.title,
      `${url.pathname}${url.search}${url.hash}`,
    );
  }

  function messageFor(error: unknown): string {
    if (error instanceof ConsoleApiError && error.status === 401) {
      return t("console.error.invalid_credentials");
    }
    if (error instanceof ConsoleApiError && error.status === 403) {
      return t("console.error.forbidden");
    }
    return t("console.error.unavailable");
  }

  function providerLabel(provider: LoginIdentity["provider"]): string {
    return provider === "email"
      ? t("console.security.email_password")
      : t(`console.identity_provider.${provider}`);
  }

  return {
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
    messageFor,
    providerLabel,
  };
}

function isPasswordRecoveryPath(url: URL | null): boolean {
  return Boolean(
    url && ["/recover", "/reset-password"].some((path) => url.pathname.endsWith(path)),
  );
}

function isAuthProvider(value: string): value is AuthProvider {
  return AUTH_PROVIDERS.has(value as AuthProvider);
}
