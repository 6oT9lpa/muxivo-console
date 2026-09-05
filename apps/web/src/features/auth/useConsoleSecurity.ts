import { ref, type Ref } from "vue";

import { consoleApi } from "../../api/consoleApi";
import type { TranslationParams } from "../../i18n";
import { clientLogger } from "../../utils/clientLogger";
import { passwordChangeValidationMessage } from "../../utils/passwordChange";
import type { BrowserSession, LoginIdentity } from "../console/types";

type Translate = (key: string, params?: TranslationParams) => string;

export type ConsoleSecurityDependencies = {
  t: Translate;
  busy: Ref<boolean>;
  notice: Ref<string>;
  authenticated: Ref<boolean>;
  messageFor: (error: unknown) => string;
};

/** Owns browser-session, identity and password-management state for the security screen. */
export function useConsoleSecurity(dependencies: ConsoleSecurityDependencies) {
  const { t, busy, notice, authenticated, messageFor } = dependencies;

  const currentPassword = ref("");
  const reauthenticationPassword = ref("");
  const newPassword = ref("");
  const confirmNewPassword = ref("");
  const browserSessions = ref<BrowserSession[]>([]);
  const loginIdentities = ref<LoginIdentity[]>([]);

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

  async function refreshSecurity(): Promise<void> {
    await Promise.all([loadBrowserSessions(), loadLoginIdentities()]);
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
      await loadBrowserSessions();
      if (!notice.value) {
        notice.value = t("console.notice.password_changed");
      }
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
      await loadBrowserSessions();
      if (!notice.value) {
        notice.value = t("console.notice.recent_auth_refreshed");
      }
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

  function resetSecurityState(): void {
    browserSessions.value = [];
    loginIdentities.value = [];
    currentPassword.value = "";
    reauthenticationPassword.value = "";
    newPassword.value = "";
    confirmNewPassword.value = "";
  }

  function providerLabel(provider: LoginIdentity["provider"]): string {
    return provider === "email"
      ? t("console.security.email_password")
      : t(`console.identity_provider.${provider}`);
  }

  return {
    currentPassword,
    reauthenticationPassword,
    newPassword,
    confirmNewPassword,
    browserSessions,
    loginIdentities,
    loadBrowserSessions,
    refreshSecurity,
    loadLoginIdentities,
    unlinkLoginIdentity,
    changePassword,
    refreshRecentAuthentication,
    resetSecurityState,
    providerLabel,
  };
}
