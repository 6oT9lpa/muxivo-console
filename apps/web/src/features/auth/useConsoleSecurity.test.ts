import { ref } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { consoleApiMock } = vi.hoisted(() => ({
  consoleApiMock: vi.fn(),
}));

vi.mock("../../api/consoleApi", () => ({
  consoleApi: consoleApiMock,
}));

import { useConsoleSecurity } from "./useConsoleSecurity";

function createSecurity() {
  const busy = ref(false);
  const notice = ref("");
  const authenticated = ref(true);
  const security = useConsoleSecurity({
    t: (key, params) =>
      params ? `${key}:${Object.values(params).join(",")}` : key,
    busy,
    notice,
    authenticated,
    messageFor: vi.fn().mockReturnValue("neutral error"),
  });
  return { security, busy, notice, authenticated };
}

const browserSession = {
  id: "session-1",
  is_current: true,
  assurance_level: "password" as const,
  authenticated_at: "2026-09-05T09:00:00Z",
  last_seen_at: "2026-09-05T09:01:00Z",
  expires_at: "2026-09-19T09:00:00Z",
  device_label: "Browser:foundation",
  ip_fingerprint: "ip:foundation",
  user_agent_fingerprint: "ua:foundation",
};

const loginIdentity = {
  id: "identity-1",
  provider: "discord" as const,
  linked_at: "2026-09-05T09:00:00Z",
  last_used_at: "2026-09-05T09:01:00Z",
  can_unlink: true,
};

describe("useConsoleSecurity", () => {
  beforeEach(() => {
    consoleApiMock.mockReset();
  });

  it("loads sessions and identities through their dedicated security boundary", async () => {
    consoleApiMock
      .mockResolvedValueOnce({ items: [browserSession] })
      .mockResolvedValueOnce({ items: [loginIdentity] });
    const { security, busy } = createSecurity();

    await security.refreshSecurity();

    expect(security.browserSessions.value).toEqual([browserSession]);
    expect(security.loginIdentities.value).toEqual([loginIdentity]);
    expect(consoleApiMock).toHaveBeenNthCalledWith(1, "/api/v1/auth/sessions");
    expect(consoleApiMock).toHaveBeenNthCalledWith(2, "/api/v1/auth/identities");
    expect(busy.value).toBe(false);
  });

  it("unlinks an identity and keeps the browser-facing provider message localized", async () => {
    consoleApiMock.mockResolvedValueOnce({});
    const { security, notice } = createSecurity();
    security.loginIdentities.value = [loginIdentity];

    await security.unlinkLoginIdentity(loginIdentity);

    expect(consoleApiMock).toHaveBeenCalledWith(
      "/api/v1/auth/identities/identity-1",
      { method: "DELETE" },
    );
    expect(security.loginIdentities.value).toEqual([]);
    expect(notice.value).toBe(
      "console.notice.identity_unlinked:console.identity_provider.discord",
    );
  });

  it("validates and changes a password, then refreshes sessions", async () => {
    const { security, notice } = createSecurity();
    security.currentPassword.value = "current-password";
    security.newPassword.value = "short";
    security.confirmNewPassword.value = "short";

    await security.changePassword();

    expect(notice.value).toBe("New password must be at least 12 characters.");
    expect(consoleApiMock).not.toHaveBeenCalled();

    consoleApiMock
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({ items: [browserSession] });
    security.newPassword.value = "a-new-long-enough-password";
    security.confirmNewPassword.value = "a-new-long-enough-password";

    await security.changePassword();

    expect(consoleApiMock).toHaveBeenNthCalledWith(1, "/api/v1/auth/password", {
      method: "PUT",
      body: JSON.stringify({
        current_password: "current-password",
        new_password: "a-new-long-enough-password",
      }),
    });
    expect(security.currentPassword.value).toBe("");
    expect(security.newPassword.value).toBe("");
    expect(security.confirmNewPassword.value).toBe("");
    expect(security.browserSessions.value).toEqual([browserSession]);
    expect(notice.value).toBe("console.notice.password_changed");
  });

  it("requires a password before refreshing recent authentication", async () => {
    const { security, notice } = createSecurity();

    await security.refreshRecentAuthentication();

    expect(notice.value).toBe("console.notice.enter_password");
    expect(consoleApiMock).not.toHaveBeenCalled();

    consoleApiMock
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({ items: [browserSession] });
    security.reauthenticationPassword.value = "current-password";

    await security.refreshRecentAuthentication();

    expect(consoleApiMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/auth/session/reauthentications",
      {
        method: "POST",
        body: JSON.stringify({ current_password: "current-password" }),
      },
    );
    expect(security.reauthenticationPassword.value).toBe("");
    expect(security.browserSessions.value).toEqual([browserSession]);
  });

  it("clears sensitive security state on sign-out and bulk revocation", () => {
    const { security } = createSecurity();
    security.browserSessions.value = [browserSession];
    security.loginIdentities.value = [loginIdentity];
    security.currentPassword.value = "current-password";
    security.reauthenticationPassword.value = "reauth-password";
    security.newPassword.value = "new-password";
    security.confirmNewPassword.value = "new-password";

    security.resetSecurityState();

    expect(security.browserSessions.value).toEqual([]);
    expect(security.loginIdentities.value).toEqual([]);
    expect(security.currentPassword.value).toBe("");
    expect(security.reauthenticationPassword.value).toBe("");
    expect(security.newPassword.value).toBe("");
    expect(security.confirmNewPassword.value).toBe("");
  });
});
