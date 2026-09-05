import { randomUUID } from "node:crypto";
import { expect, test, type Page, type Route } from "@playwright/test";

const organizationId = "11111111-1111-4111-8111-111111111111";
const ownerMembershipId = "22222222-2222-4222-8222-222222222222";
const ownerUserId = "33333333-3333-4333-8333-333333333333";
const memberMembershipId = "77777777-7777-4777-8777-777777777777";
const memberUserId = "88888888-8888-4888-8888-888888888888";
const memberScopeId = "99999999-9999-4999-8999-999999999999";
const discordIdentityId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const emailIdentityId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const connectionId = "44444444-4444-4444-8444-444444444444";
const browserSessionId = "55555555-5555-4555-8555-555555555555";
const invitationId = "66666666-6666-4666-8666-666666666666";
const externalResourceId = "123456789012345678";

type PlatformConnection = {
  id: string;
  organization_id: string;
  platform: "discord" | "twitch";
  external_resource_id: string;
  status: "active" | "reauth_required" | "disconnected";
  status_reason: "healthy" | "revoked" | "reauthorized" | "disconnected";
  granted_scopes: PlatformConnectionGrantedScope[];
};

type PlatformConnectionGrantedScope = {
  key: string;
  display_name: string;
  description: string;
  status: "granted" | "requires_reauthorization" | "revoked";
};

test("sign-in, organization, connection lifecycle and security from the browser", async ({
  page,
}) => {
  const state = {
    authenticated: false,
    registeredEmail: "",
    organizations: [] as unknown[],
    organizationMembers: [] as unknown[],
    invitations: [] as unknown[],
    connections: [] as PlatformConnection[],
    auditEvents: [] as unknown[],
    observedLifecycleIdempotencyKey: "",
  };
  await page.context().addCookies([
    {
      name: "muxivo_console_dev_csrf",
      value: "csrf-token",
      url: "http://127.0.0.1:5173",
      sameSite: "Lax",
    },
  ]);
  await installConsoleApiMock(page, state);

  await page.goto("/");

  await page.getByRole("button", { name: /see panel|открыть панель/i }).click();
  await page.getByRole("tab", { name: "Create account" }).click();
  await expect(
    page.getByRole("heading", { name: "Create your Console account." }),
  ).toBeVisible();
  await page.getByLabel("Display name").fill("Creator");
  await page.getByLabel("Email", { exact: true }).fill("creator@example.com");
  await page.getByLabel("Password", { exact: true }).fill("a-long-enough-password");
  await page.getByRole("button", { name: "Create Console account" }).click();

  await expect(page.getByRole("dialog").locator(".auth-notice")).toContainText(
    "a six-digit confirmation code is on its way",
  );
  expect(state.registeredEmail).toBe("creator@example.com");

  await page.getByLabel("6-digit confirmation code").fill("123456");
  await page.getByRole("button", { name: "Confirm e-mail" }).click();
  await expect(page.getByRole("dialog").locator(".auth-notice")).toContainText(
    "E-mail confirmed. Sign in to open Muxivo Console",
  );
  await page.getByRole("button", { name: "Continue to sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();

  const signInEmail = page.locator("#console-auth-email");
  const signInPassword = page.locator("#console-auth-password");
  await expect(signInPassword).toBeVisible();
  await signInEmail.fill("creator@example.com");
  await signInPassword.fill("a-long-enough-password");
  await page.getByRole("button", { name: "Sign in to Console" }).click();

  await expect(page.getByRole("heading", { name: "Overview", level: 1 })).toBeVisible();
  await expect(page.getByRole("button", { name: "Link Google" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Link Yandex ID" })).toBeDisabled();
  await page.getByRole("button", { name: "Security", exact: true }).click();
  await expect(page.locator("#console-security")).toBeVisible();
  await page.getByRole("button", { name: "Switch to light theme" }).last().click();
  await expect(page.locator(".muxivo-app")).toHaveClass(/theme-light/);
  await page.getByRole("button", { name: "Switch to dark theme" }).last().click();
  await expect(page.locator(".muxivo-app")).toHaveClass(/theme-dark/);
  await expect(page.getByText("Browser:foundation · current")).toBeVisible();
  await expect(page.getByText("Ready to revoke every active browser session.")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Create your first organization" }),
  ).toBeVisible();

  await page.getByLabel("Organization name").fill("Creator community");
  await page.getByRole("button", { name: "Create organization" }).click();

  await expect(page.getByRole("status")).toContainText(
    "Organization Creator community is ready",
  );
  await expect(
    page.locator("#console-overview").getByRole("heading", { name: "Create an organization" }),
  ).toHaveCount(0);
  await expect(
    page.locator("#console-overview").getByRole("heading", { name: "Creator community" }),
  ).toBeVisible();
  const organizationSwitcher = page.locator("#console-connections-organization-select");
  await expect(organizationSwitcher).toHaveValue(organizationId);
  await expect
    .poll(() =>
      page.evaluate(() => localStorage.getItem("muxivo.console.activeOrganizationId")),
    )
    .toBe(organizationId);

  const membersSection = page.locator("#console-members");
  await membersSection.getByLabel("Email", { exact: true }).fill("invitee@example.com");
  await membersSection.getByRole("button", { name: "Invite member" }).click();
  await expect(page.getByRole("status")).toContainText("Organization member invited.");
  await expect(membersSection).toContainText("i***@example.com");
  await membersSection.getByRole("button", { name: "Revoke invitation" }).click();
  await expect(page.getByRole("status")).toContainText("Organization invitation revoked.");
  await expect(membersSection).toContainText("Revoked");

  const memberRow = membersSection.locator("li").filter({ hasText: "Scoped member" });
  await expect(memberRow).toContainText("Viewer");
  await memberRow.locator("select").selectOption("moderator");
  await expect(page.getByRole("status")).toContainText("Organization member updated.");
  await expect(memberRow).toContainText("Moderator");
  const memberScope = memberRow.getByRole("checkbox").first();
  await expect(memberScope).toBeChecked();
  await memberScope.uncheck();
  await expect(page.getByRole("status")).toContainText("Organization member updated.");
  await expect(memberRow).toContainText("0 scopes");
  await memberRow.getByRole("button", { name: "Remove" }).click();
  await expect(page.getByRole("status")).toContainText("Organization member removed.");
  await expect(memberRow).toHaveCount(0);

  const connectionWizard = page.locator(
    "section[aria-labelledby='connection-wizard-heading']",
  );
  await expect(connectionWizard).toContainText("Link the matching Discord identity.");
  await expect(connectionWizard).toContainText(
    "Verify Discord server ownership through the Control API.",
  );
  await expect(connectionWizard).not.toContainText("Telegram");

  await connectionWizard.getByRole("button", { name: /Connect Twitch channel/ }).click();
  await expect(page.getByRole("heading", { name: "Connect Twitch channel" })).toBeVisible();
  await expect(connectionWizard).toContainText("Link the matching Twitch identity.");
  await expect(connectionWizard).toContainText(
    "Verify Twitch broadcaster ownership through the Control API.",
  );
  await expect(page.getByLabel("Available Twitch channels")).toBeVisible();
  await expect(
    connectionWizard.getByRole("button", { name: "Link Twitch identity" }),
  ).toBeVisible();

  await connectionWizard.getByRole("button", { name: /Connect Discord server/ }).click();
  await expect(
    connectionWizard.getByRole("button", { name: "Link Discord identity" }),
  ).toBeVisible();
  const discordCandidateSelect = page.getByLabel("Available Discord servers");
  await expect(discordCandidateSelect).toBeVisible();
  await discordCandidateSelect.selectOption(externalResourceId);
  await page.getByRole("button", { name: "Connect Discord server" }).last().click();

  const connectionRow = page.locator("li").filter({ hasText: externalResourceId });
  await expect(connectionRow).toContainText(externalResourceId);
  await expect(connectionRow).toContainText("Active");
  await expect(connectionRow).toContainText("Read Discord server metadata");
  await expect(connectionRow).toContainText("Manage Discord server settings");
  await expect(connectionRow).toContainText("Granted");
  await page.getByRole("button", { name: "Load health" }).click();
  await expect(page.getByText("Bot latency")).toBeVisible();
  await expect(page.getByText("12 ms")).toBeVisible();

  await page.getByRole("button", { name: "Load audit log" }).click();
  await expect(page.getByText("organization.created")).toBeVisible();
  await expect(page.getByText("organization.member.update")).toHaveCount(2);
  await expect(page.getByText("organization.member.remove")).toHaveCount(1);
  await expect(page.getByText("platform_connection.connect")).toBeVisible();

  await connectionRow.getByRole("button", { name: "Revoke" }).click();

  await expect(page.getByRole("status")).toContainText(
    "Discord connection is now Reauthorization required.",
  );
  await expect(connectionRow).toContainText("Reauthorization required");
  await expect(connectionRow).toContainText(
    "Reason: Platform access was revoked by an organization manager.",
  );
  expect(state.observedLifecycleIdempotencyKey).toBe(`revoke:${connectionId}`);

  await connectionRow.getByRole("button", { name: "Reauthorize" }).click();
  await expect(page.getByRole("status")).toContainText("Discord connection is now Active.");
  await expect(connectionRow).toContainText("Active");
  expect(state.observedLifecycleIdempotencyKey).toBe(`reauthorize:${connectionId}`);

  await connectionRow.getByRole("button", { name: "Disconnect" }).click();
  await expect(page.getByRole("status")).toContainText("Discord connection is now Disconnected.");
  await expect(connectionRow).toContainText("Disconnected");
  await expect(connectionRow).toContainText("Risky actions are blocked for this state.");
  await expect(connectionRow.getByRole("button", { name: "Revoke" })).toBeDisabled();
  await expect(connectionRow.getByRole("button", { name: "Disconnect" })).toBeDisabled();
  expect(state.observedLifecycleIdempotencyKey).toBe(`disconnect:${connectionId}`);

  await page.getByRole("button", { name: "Load audit log" }).click();
  await expect(page.getByText("platform_connection.revoke")).toBeVisible();
  await expect(page.getByText("platform_connection.reauthorize")).toBeVisible();
  await expect(page.getByText("platform_connection.disconnect")).toBeVisible();

  await page.getByRole("button", { name: "Security", exact: true }).click();
  await page
    .locator("#console-security")
    .getByRole("button", { name: "Revoke current session" })
    .click();
  await expect(page.getByRole("button", { name: "See Panel" })).toBeVisible();
  expect(state.authenticated).toBe(false);
});

test("security screen manages recent authentication, identities and password safeguards", async ({
  page,
}) => {
  const state = {
    authenticated: true,
    registeredEmail: "",
    organizations: [] as unknown[],
    organizationMembers: [] as unknown[],
    invitations: [] as unknown[],
    connections: [] as PlatformConnection[],
    auditEvents: [] as unknown[],
    observedLifecycleIdempotencyKey: "",
    loginIdentities: [
      {
        id: emailIdentityId,
        provider: "email",
        linked_at: "2026-09-01T12:00:00Z",
        last_used_at: "2026-09-05T12:00:00Z",
        can_unlink: false,
      },
      {
        id: discordIdentityId,
        provider: "discord",
        linked_at: "2026-09-02T12:00:00Z",
        last_used_at: "2026-09-04T12:00:00Z",
        can_unlink: true,
      },
    ],
  };
  await page.context().addCookies([
    {
      name: "muxivo_console_dev_csrf",
      value: "csrf-token",
      url: "http://127.0.0.1:5173",
      sameSite: "Lax",
    },
  ]);
  await installConsoleApiMock(page, state);

  await page.goto("/");
  await page.getByRole("button", { name: "Security", exact: true }).click();

  const security = page.locator("#console-security");
  await expect(security).toContainText("Browser:foundation · current");
  const recentAuthenticationForm = security.locator("form").first();
  await recentAuthenticationForm
    .getByLabel("Refresh recent authentication")
    .fill("current-password");
  await recentAuthenticationForm
    .getByRole("button", { name: "Confirm current password" })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "Recent authentication refreshed for this browser session.",
  );

  await expect(security.getByRole("button", { name: "Unlink" })).toBeVisible();
  await security.getByRole("button", { name: "Unlink" }).click();
  await expect(page.getByRole("status")).toContainText("Discord login identity unlinked.");
  await expect(security.getByRole("button", { name: "Unlink" })).toHaveCount(0);
  await expect(security.getByRole("button", { name: "Protected" })).toBeDisabled();

  const passwordForm = security.locator("form").nth(1);
  await passwordForm.getByLabel("Current password").fill("current-password");
  await passwordForm.getByLabel("New password", { exact: true }).fill("a-new-long-enough-password");
  await passwordForm
    .getByLabel("Confirm new password", { exact: true })
    .fill("a-new-long-enough-password");
  await passwordForm.getByRole("button", { name: "Change password" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Password changed. Keep your recovery options up to date.",
  );

  await security.getByRole("button", { name: "Revoke all sessions" }).click();
  await expect(page.getByRole("button", { name: "See Panel" })).toBeVisible();
  expect(state.authenticated).toBe(false);
});

test("landing page and sign-in dialog fit a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.waitForTimeout(2500);

  expect(
    await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
  ).toBe(false);

  await page.getByRole("button", { name: /see panel|открыть панель/i }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog).toHaveAttribute("aria-labelledby", "console-auth-dialog-title");
  await expect(dialog.locator("#console-auth-email")).toBeFocused();
  const lastFocusableControl = dialog.locator("button:not([disabled])").last();
  await lastFocusableControl.focus();
  await page.keyboard.press("Tab");
  await expect(dialog.getByRole("button", { name: /Close/ })).toBeFocused();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
  ).toBe(false);
});

test("authenticated Console shell stays usable in a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const state = {
    authenticated: true,
    registeredEmail: "",
    organizations: [
      {
        organization: {
          id: organizationId,
          name: "Creator community",
          slug: "creator-community",
        },
        membership: {
          id: ownerMembershipId,
          organization_id: organizationId,
          user_id: ownerUserId,
          display_name: "Creator",
          role: "owner",
          resource_scopes: [],
        },
      },
    ],
    organizationMembers: [],
    invitations: [],
    connections: [],
    auditEvents: [],
    observedLifecycleIdempotencyKey: "",
  };
  await page.context().addCookies([
    {
      name: "muxivo_console_dev_csrf",
      value: "csrf-token",
      url: "http://127.0.0.1:5173",
      sameSite: "Lax",
    },
  ]);
  await installConsoleApiMock(page, state);

  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Overview", level: 1 })).toBeVisible();
  await expect(page.getByLabel("Active organization").first()).toHaveValue(organizationId);
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
  ).toBe(false);

  await page.getByRole("button", { name: "Members", exact: true }).click();
  await expect(page.locator("#console-members")).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
  ).toBe(false);

  await page.getByRole("button", { name: "Connections", exact: true }).click();
  await expect(page.locator("#console-connections")).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
  ).toBe(false);
});

test("sign-in dialog keeps the Activity-style black surface in light theme", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await installConsoleApiMock(page, {
    authenticated: false,
    registeredEmail: "",
    organizations: [],
    organizationMembers: [],
    invitations: [],
    connections: [],
    auditEvents: [],
    observedLifecycleIdempotencyKey: "",
  });
  await page.goto("/");

  await page
    .getByRole("button", { name: /switch to light theme|включить светлую тему/i })
    .click();
  await page.getByRole("button", { name: /see panel|открыть панель/i }).click();

  const panel = page.locator(".login-panel");
  await expect(panel).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue with Twitch" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Continue with Google" })).toBeDisabled();
  const styleState = await panel.evaluate((element) => {
    const title = element.querySelector("#console-auth-dialog-title");
    const description = element.querySelector(".auth-panel-heading > p");
    const shader = element.parentElement?.querySelector(".auth-shader");
    return {
      panelColor: getComputedStyle(element).color,
      panelBackgroundColor: getComputedStyle(element).backgroundColor,
      titleColor: title ? getComputedStyle(title).color : "",
      descriptionColor: description ? getComputedStyle(description).color : "",
      shaderBackgroundImage: shader ? getComputedStyle(shader).backgroundImage : "",
    };
  });

  expect(styleState.panelBackgroundColor).toBe("rgb(5, 5, 5)");
  expect(styleState.panelColor).toBe("rgb(244, 244, 245)");
  expect(styleState.titleColor).toBe("rgb(250, 250, 250)");
  expect(styleState.descriptionColor).toBe("rgb(161, 161, 170)");
  expect(styleState.shaderBackgroundImage).toContain("radial-gradient");
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
  ).toBe(false);
});

test("auth modal exposes the anti-enumeration recovery flow", async ({ page }) => {
  const state = {
    authenticated: false,
    registeredEmail: "",
    organizations: [] as unknown[],
    organizationMembers: [],
    invitations: [] as unknown[],
    connections: [] as PlatformConnection[],
    auditEvents: [],
    observedLifecycleIdempotencyKey: "",
  };
  await page.context().addCookies([
    {
      name: "muxivo_console_dev_csrf",
      value: "csrf-token",
      url: "http://127.0.0.1:5173",
      sameSite: "Lax",
    },
  ]);
  await installConsoleApiMock(page, state);

  await page.goto("/");
  await page.getByRole("button", { name: "See Panel" }).click();
  await page.getByRole("button", { name: "Forgot password?" }).click();
  await expect(page.locator("#console-auth-recovery-email")).toBeFocused();
  await page.getByLabel("Account email").fill("creator@example.com");
  await page.getByRole("button", { name: "Request reset" }).click();
  await expect(page.getByRole("dialog").locator(".auth-notice")).toContainText(
    "instructions will be sent",
  );

  await page.goto("/recover?token=recovery-token");
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.locator("#console-auth-recovery-token")).toHaveValue(
    "recovery-token",
  );
  await page.getByLabel("New password", { exact: true }).fill("a-new-long-enough-password");
  await page
    .getByLabel("Confirm new password", { exact: true })
    .fill("a-new-long-enough-password");
  await page.getByRole("button", { name: "Reset password" }).click();
  await expect(page.getByRole("dialog").locator(".auth-notice")).toContainText(
    "Password reset. Sign in with your new password.",
  );
});

test("language switcher updates the public document and persists the locale", async ({ page }) => {
  await page.goto("/");

  const languageTrigger = page.getByTestId("language-menu-trigger").first();
  await languageTrigger.click();
  await expect(page.getByTestId("language-menu")).toBeVisible();
  await page.locator("[role='menuitemradio'][lang='ru']").click();

  await expect(page.locator("html")).toHaveAttribute("lang", "ru");
  await expect(page.getByRole("button", { name: "Открыть панель" })).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => localStorage.getItem("muxivo-discord.activity.locale")))
    .toBe("ru");

  await languageTrigger.click();
  await page.locator("[role='menuitemradio'][lang='en']").click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("button", { name: "See Panel" })).toBeVisible();
});

async function installConsoleApiMock(
  page: Page,
  state: {
    authenticated: boolean;
    registeredEmail: string;
    organizations: unknown[];
    organizationMembers: unknown[];
    invitations: unknown[];
    connections: PlatformConnection[];
    auditEvents: unknown[];
    observedLifecycleIdempotencyKey: string;
    loginIdentities?: unknown[];
  },
) {
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (["DELETE", "PATCH", "POST", "PUT"].includes(method)) {
      expect(request.headers()["x-csrf-token"]).toBe("csrf-token");
    }

    if (method === "GET" && path === "/api/v1/auth/providers") {
      return json(route, { providers: ["discord", "twitch"] });
    }
    if (method === "GET" && path === "/api/v1/auth/session") {
      return state.authenticated
        ? json(route, { authenticated: true })
        : json(route, { detail: "Access denied" }, 403);
    }
    if (method === "POST" && path === "/api/v1/auth/email-password/registrations") {
      const payload = JSON.parse(request.postData() ?? "{}");
      expect(payload).toMatchObject({
        display_name: "Creator",
        email: "creator@example.com",
        password: "a-long-enough-password",
      });
      state.registeredEmail = payload.email;
      return json(
        route,
        { status: "verification_required", verification_token: "registration-token" },
        202,
      );
    }
    if (
      method === "POST" &&
      path === "/api/v1/auth/email-password/registration-verifications"
    ) {
      const payload = JSON.parse(request.postData() ?? "{}");
      expect(payload).toEqual({ token: "registration-token", code: "123456" });
      return json(route, { status: "verified" });
    }
    if (
      method === "POST" &&
      path === "/api/v1/auth/email-password/registration-verifications/resend"
    ) {
      const payload = JSON.parse(request.postData() ?? "{}");
      expect(payload).toEqual({ token: "registration-token" });
      return json(
        route,
        { status: "verification_required", verification_token: "registration-token" },
        202,
      );
    }
    if (method === "POST" && path === "/api/v1/auth/email-password/sessions") {
      state.authenticated = true;
      return empty(route);
    }
    if (method === "POST" && path === "/api/v1/auth/password-recovery/requests") {
      const payload = JSON.parse(request.postData() ?? "{}");
      expect(payload).toEqual({ email: "creator@example.com" });
      return json(route, { status: "accepted" });
    }
    if (method === "POST" && path === "/api/v1/auth/password-recovery/completions") {
      const payload = JSON.parse(request.postData() ?? "{}");
      expect(payload).toEqual({
        token: "recovery-token",
        new_password: "a-new-long-enough-password",
      });
      return empty(route);
    }
    if (method === "GET" && path === "/api/v1/auth/sessions") {
      return json(route, {
        items: [
          {
            id: browserSessionId,
            is_current: true,
            assurance_level: "recent_authentication",
            authenticated_at: "2026-08-22T12:00:00Z",
            last_seen_at: "2026-08-22T12:01:00Z",
            expires_at: "2026-09-05T12:00:00Z",
            device_label: "Browser:foundation",
            ip_fingerprint: "ip:foundation",
            user_agent_fingerprint: "ua:foundation",
          },
        ],
      });
    }
    if (method === "GET" && path === "/api/v1/auth/identities") {
      return json(route, { items: state.loginIdentities ?? [] });
    }
    if (method === "POST" && path === "/api/v1/auth/session/reauthentications") {
      const payload = JSON.parse(request.postData() ?? "{}");
      expect(payload).toEqual({ current_password: "current-password" });
      return empty(route);
    }
    if (method === "PUT" && path === "/api/v1/auth/password") {
      const payload = JSON.parse(request.postData() ?? "{}");
      expect(payload).toEqual({
        current_password: "current-password",
        new_password: "a-new-long-enough-password",
      });
      return empty(route);
    }
    if (method === "DELETE" && path.startsWith("/api/v1/auth/identities/")) {
      const identityId = path.split("/").at(-1);
      state.loginIdentities = (state.loginIdentities ?? []).filter(
        (identity) => (identity as { id?: string }).id !== identityId,
      );
      return empty(route);
    }
    if (method === "DELETE" && path === "/api/v1/auth/session") {
      state.authenticated = false;
      return empty(route);
    }
    if (method === "DELETE" && path === "/api/v1/auth/sessions") {
      state.authenticated = false;
      return json(route, { revoked_count: 2 });
    }
    if (method === "GET" && path === "/api/v1/organizations") {
      return json(route, { items: state.organizations });
    }
    if (method === "POST" && path === "/api/v1/organizations") {
      const organization = {
        id: organizationId,
        name: "Creator community",
        slug: "creator-community",
      };
      state.organizations = [
        {
          organization,
          membership: {
            id: ownerMembershipId,
            organization_id: organizationId,
            user_id: ownerUserId,
            display_name: "Creator",
            role: "owner",
            resource_scopes: [],
          },
        },
      ];
      state.organizationMembers = [
        {
          id: ownerMembershipId,
          organization_id: organizationId,
          user_id: ownerUserId,
          display_name: "Creator",
          role: "owner",
          resource_scopes: [],
        },
        {
          id: memberMembershipId,
          organization_id: organizationId,
          user_id: memberUserId,
          display_name: "Scoped member",
          role: "viewer",
          resource_scopes: [
            {
              id: memberScopeId,
              resource: "console.control_modules",
              action: "read",
            },
          ],
        },
      ];
      state.auditEvents.push(auditEvent("organization.created", "organization", organizationId));
      return json(route, organization, 201);
    }
    if (method === "GET" && path === `/api/v1/organizations/${organizationId}/members`) {
      return json(route, { items: state.organizationMembers });
    }
    if (method === "PUT" && path === `/api/v1/organizations/${organizationId}/members/${memberUserId}`) {
      const payload = JSON.parse(request.postData() ?? "{}");
      expect(payload.role).toBe("moderator");
      const updated = {
        ...(state.organizationMembers.find(
          (item) => (item as { user_id?: string }).user_id === memberUserId,
        ) as Record<string, unknown>),
        role: payload.role,
        resource_scopes: payload.resource_scopes.map(
          (scope: { resource: string; action: string }) => ({
            id: payload.resource_scopes.length ? memberScopeId : null,
            resource: scope.resource,
            action: scope.action,
          }),
        ),
      };
      state.organizationMembers = state.organizationMembers.map((item) =>
        (item as { user_id?: string }).user_id === memberUserId ? updated : item,
      );
      state.auditEvents.push(
        auditEvent("organization.member.update", "organization_member", memberUserId),
      );
      return json(route, updated);
    }
    if (method === "DELETE" && path === `/api/v1/organizations/${organizationId}/members/${memberUserId}`) {
      state.organizationMembers = state.organizationMembers.filter(
        (item) => (item as { user_id?: string }).user_id !== memberUserId,
      );
      state.auditEvents.push(
        auditEvent("organization.member.remove", "organization_member", memberUserId),
      );
      return empty(route);
    }
    if (method === "GET" && path === `/api/v1/organizations/${organizationId}/member-invitations`) {
      return json(route, { items: state.invitations });
    }
    if (method === "POST" && path === `/api/v1/organizations/${organizationId}/member-invitations`) {
      const payload = JSON.parse(request.postData() ?? "{}");
      expect(payload).toMatchObject({
        email: "invitee@example.com",
        role: "viewer",
      });
      const invitation = {
        id: invitationId,
        organization_id: organizationId,
        email_hint: "i***@example.com",
        role: "viewer",
        resource_scopes: [
          { id: null, resource: "console.control_modules", action: "read" },
        ],
        status: "pending",
        expires_at: "2026-09-09T12:00:00Z",
        created_at: "2026-09-02T12:00:00Z",
        accepted_at: null,
        revoked_at: null,
        delivery_status: "sent",
      };
      state.invitations = [invitation];
      state.auditEvents.push(
        auditEvent("organization.member.invitation.created", "organization_invitation", invitationId),
      );
      return json(route, invitation, 202);
    }
    if (
      method === "DELETE" &&
      path === `/api/v1/organizations/${organizationId}/member-invitations/${invitationId}`
    ) {
      state.invitations = state.invitations.map((invitation) => ({
        ...(invitation as Record<string, unknown>),
        status: "revoked",
        revoked_at: "2026-09-02T12:01:00Z",
      }));
      state.auditEvents.push(
        auditEvent("organization.member.invitation.revoked", "organization_invitation", invitationId),
      );
      return empty(route);
    }
    if (
      method === "GET" &&
      path === `/api/v1/organizations/${organizationId}/platform-connection-candidates`
    ) {
      const requestedPlatform = new URL(request.url()).searchParams.get("platform");
      return json(route, {
        platform: requestedPlatform,
        identity_linked: true,
        items: [
          {
            platform: requestedPlatform,
            external_resource_id: externalResourceId,
            display_name:
              requestedPlatform === "discord" ? "Muxivo Discord Community" : "Muxivo Twitch channel",
          },
        ],
      });
    }
    if (
      method === "GET" &&
      path === `/api/v1/organizations/${organizationId}/platform-connections`
    ) {
      return json(route, { items: state.connections, next_cursor: null });
    }
    if (
      method === "GET" &&
      path === `/api/v1/organizations/${organizationId}/platforms/discord/health`
    ) {
      return json(route, {
        organization_id: organizationId,
        platform: "discord",
        signals: [
          {
            key: "discord.bot-latency",
            display_name: "Bot latency",
            value: "12 ms",
            status: "operational",
            latency_ms: 12,
          },
        ],
      });
    }
    if (
      method === "POST" &&
      path === `/api/v1/organizations/${organizationId}/platform-connections`
    ) {
      const connection: PlatformConnection = {
        id: connectionId,
        organization_id: organizationId,
        platform: JSON.parse(request.postData() ?? "{}").platform,
        external_resource_id: externalResourceId,
        status: "active",
        status_reason: "healthy",
        granted_scopes: discordGrantedScopes("granted"),
      };
      state.connections = [connection];
      state.auditEvents.push(
        auditEvent("platform_connection.connect", "platform_connection", connectionId),
      );
      return json(route, connection, 201);
    }
    if (
      method === "GET" &&
      path === `/api/v1/organizations/${organizationId}/audit-events`
    ) {
      return json(route, { items: state.auditEvents, next_cursor: null });
    }
    if (
      method === "POST" &&
      path ===
        `/api/v1/organizations/${organizationId}/platform-connections/${connectionId}/revocations`
    ) {
      state.observedLifecycleIdempotencyKey = request.headers()["idempotency-key"] ?? "";
      const updated = {
        ...state.connections[0],
        status: "reauth_required" as const,
        status_reason: "revoked" as const,
        granted_scopes: discordGrantedScopes("requires_reauthorization"),
      };
      state.connections = [updated];
      state.auditEvents.push(
        auditEvent("platform_connection.revoke", "platform_connection", connectionId),
      );
      return json(route, updated);
    }
    if (
      method === "POST" &&
      path ===
        `/api/v1/organizations/${organizationId}/platform-connections/${connectionId}/reauthorizations`
    ) {
      state.observedLifecycleIdempotencyKey = request.headers()["idempotency-key"] ?? "";
      const updated = {
        ...state.connections[0],
        status: "active" as const,
        status_reason: "reauthorized" as const,
        granted_scopes: discordGrantedScopes("granted"),
      };
      state.connections = [updated];
      state.auditEvents.push(
        auditEvent("platform_connection.reauthorize", "platform_connection", connectionId),
      );
      return json(route, updated);
    }
    if (
      method === "DELETE" &&
      path ===
        `/api/v1/organizations/${organizationId}/platform-connections/${connectionId}`
    ) {
      state.observedLifecycleIdempotencyKey = request.headers()["idempotency-key"] ?? "";
      const updated = {
        ...state.connections[0],
        status: "disconnected" as const,
        status_reason: "disconnected" as const,
        granted_scopes: discordGrantedScopes("revoked"),
      };
      state.connections = [updated];
      state.auditEvents.push(
        auditEvent("platform_connection.disconnect", "platform_connection", connectionId),
      );
      return json(route, updated);
    }
    return json(route, { detail: `Unhandled ${method} ${path}` }, 500);
  });
}

function discordGrantedScopes(
  status: PlatformConnectionGrantedScope["status"],
): PlatformConnectionGrantedScope[] {
  return [
    {
      key: "discord.guild.read",
      display_name: "Read Discord server metadata",
      description: "Lets Console show safe aggregate server, channel and health information.",
      status,
    },
    {
      key: "discord.guild.manage",
      display_name: "Manage Discord server settings",
      description:
        "Lets Console request server-side Control API changes after native admin checks.",
      status,
    },
  ];
}

function auditEvent(action: string, resourceType: string, resourceId: string) {
  return {
    id: randomUUID(),
    correlation_id: randomUUID(),
    actor_id: ownerUserId,
    action,
    resource_type: resourceType,
    resource_id: resourceId,
    result: "succeeded",
    created_at: "2026-08-22T12:00:00Z",
  };
}

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function empty(route: Route) {
  await route.fulfill({ status: 204 });
}
