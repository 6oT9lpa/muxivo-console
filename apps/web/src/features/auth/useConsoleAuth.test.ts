import { ref } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { consoleApiMock } = vi.hoisted(() => ({
  consoleApiMock: vi.fn(),
}));

vi.mock("../../api/consoleApi", () => ({
  consoleApi: consoleApiMock,
  ConsoleApiError: class ConsoleApiError extends Error {
    status = 0;
  },
}));

import { useConsoleAuth } from "./useConsoleAuth";

function createAuth() {
  const busy = ref(false);
  const notice = ref("");
  const authenticated = ref(false);
  const dependencies = {
    t: (key: string) => key,
    busy,
    notice,
    authenticated,
    closeLoginModal: vi.fn(),
    loadOrganizations: vi.fn().mockResolvedValue(undefined),
    acceptInvitationIfPresent: vi.fn().mockResolvedValue(undefined),
  };
  return { auth: useConsoleAuth(dependencies), ...dependencies };
}

describe("useConsoleAuth", () => {
  beforeEach(() => {
    consoleApiMock.mockReset();
  });

  it("keeps only server-advertised supported OAuth providers", async () => {
    consoleApiMock.mockResolvedValue({ providers: ["discord", "unknown", "google"] });
    const { auth } = createAuth();

    await auth.loadAuthProviders();

    expect(auth.availableAuthProviders.value).toEqual(["discord", "google"]);
  });

  it("sends recovery requests through the anti-enumeration contract", async () => {
    consoleApiMock.mockResolvedValue({ status: "accepted" });
    const { auth, notice } = createAuth();
    auth.recoveryEmail.value = "creator@example.com";

    await auth.requestPasswordRecovery();

    expect(consoleApiMock).toHaveBeenCalledWith(
      "/api/v1/auth/password-recovery/requests",
      {
        method: "POST",
        body: JSON.stringify({ email: "creator@example.com" }),
      },
    );
    expect(notice.value).toBe("console.notice.recovery_requested");
  });

  it("coordinates sign-in state and post-authentication hydration", async () => {
    consoleApiMock
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce({ items: [] })
      .mockResolvedValueOnce({ items: [] });
    const { auth, authenticated, closeLoginModal, loadOrganizations, acceptInvitationIfPresent } =
      createAuth();
    auth.email.value = "creator@example.com";
    auth.password.value = "a-long-enough-password";

    await auth.signIn();

    expect(authenticated.value).toBe(true);
    expect(closeLoginModal).toHaveBeenCalledOnce();
    expect(loadOrganizations).toHaveBeenCalledOnce();
    expect(acceptInvitationIfPresent).toHaveBeenCalledOnce();
    expect(auth.password.value).toBe("");
  });
});

