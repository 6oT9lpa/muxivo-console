import { randomUUID } from "node:crypto";
import { expect, test, type Page, type Route } from "@playwright/test";

const organizationId = "11111111-1111-4111-8111-111111111111";
const ownerMembershipId = "22222222-2222-4222-8222-222222222222";
const ownerUserId = "33333333-3333-4333-8333-333333333333";
const connectionId = "44444444-4444-4444-8444-444444444444";
const browserSessionId = "55555555-5555-4555-8555-555555555555";
const externalResourceId = "123456789012345678";

type PlatformConnection = {
  id: string;
  organization_id: string;
  platform: "discord" | "twitch";
  external_resource_id: string;
  status: "active" | "reauth_required";
  granted_scopes: PlatformConnectionGrantedScope[];
};

type PlatformConnectionGrantedScope = {
  key: string;
  display_name: string;
  description: string;
  status: "granted" | "requires_reauthorization";
};

test("sign-in, create organization, connect Discord, audit and revoke from the browser", async ({
  page,
}) => {
  const state = {
    authenticated: false,
    registeredEmail: "",
    organizations: [] as unknown[],
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

  await expect(page.getByRole("status")).toContainText(
    "Account accepted. Sign in with your password",
  );
  expect(state.registeredEmail).toBe("creator@example.com");

  await page.getByLabel("Email", { exact: true }).fill("creator@example.com");
  await page.getByLabel("Password", { exact: true }).fill("a-long-enough-password");
  await page.getByRole("button", { name: "Sign in to Console" }).click();

  await expect(page.getByRole("heading", { name: "Overview", level: 1 })).toBeVisible();
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
  const organizationSwitcher = page
    .locator(".identity-link")
    .filter({ hasText: "Active organization" })
    .locator("select");
  await expect(organizationSwitcher).toHaveValue(organizationId);
  await expect
    .poll(() =>
      page.evaluate(() => localStorage.getItem("muxivo.console.activeOrganizationId")),
    )
    .toBe(organizationId);

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
  await expect(page.getByLabel("Twitch channel ID")).toBeVisible();
  await expect(
    connectionWizard.getByRole("button", { name: "Link Twitch identity" }),
  ).toBeVisible();

  await connectionWizard.getByRole("button", { name: /Connect Discord server/ }).click();
  await expect(
    connectionWizard.getByRole("button", { name: "Link Discord identity" }),
  ).toBeVisible();
  await page.getByLabel("Discord server ID").fill(externalResourceId);
  await page.getByRole("button", { name: "Connect Discord server" }).last().click();

  const connectionRow = page.locator("li").filter({ hasText: externalResourceId });
  await expect(connectionRow).toContainText(externalResourceId);
  await expect(connectionRow).toContainText("Active");
  await expect(connectionRow).toContainText("Read Discord server metadata");
  await expect(connectionRow).toContainText("Manage Discord server settings");
  await expect(connectionRow).toContainText("Granted");

  await page.getByRole("button", { name: "Load audit log" }).click();
  await expect(page.getByText("organization.created")).toBeVisible();
  await expect(page.getByText("platform_connection.register")).toBeVisible();

  await connectionRow.getByRole("button", { name: "Revoke" }).click();

  await expect(page.getByRole("status")).toContainText(
    "Discord connection is now Reauthorization required.",
  );
  await expect(connectionRow).toContainText("Reauthorization required");
  expect(state.observedLifecycleIdempotencyKey).toBe(`revoke:${connectionId}`);

  await page.getByRole("button", { name: "Load audit log" }).click();
  await expect(page.getByText("platform_connection.revoke")).toBeVisible();
});

async function installConsoleApiMock(
  page: Page,
  state: {
    authenticated: boolean;
    registeredEmail: string;
    organizations: unknown[];
    connections: PlatformConnection[];
    auditEvents: unknown[];
    observedLifecycleIdempotencyKey: string;
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
      return json(route, { status: "accepted" }, 202);
    }
    if (method === "POST" && path === "/api/v1/auth/email-password/sessions") {
      state.authenticated = true;
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
      return json(route, { items: [] });
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
            role: "owner",
            resource_scopes: [],
          },
        },
      ];
      state.auditEvents.push(auditEvent("organization.created", "organization", organizationId));
      return json(route, organization, 201);
    }
    if (method === "GET" && path === `/api/v1/organizations/${organizationId}/members`) {
      return json(route, {
        items: [
          {
            id: ownerMembershipId,
            organization_id: organizationId,
            user_id: ownerUserId,
            role: "owner",
            resource_scopes: [],
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
      method === "POST" &&
      path === `/api/v1/organizations/${organizationId}/platform-connections`
    ) {
      const connection: PlatformConnection = {
        id: connectionId,
        organization_id: organizationId,
        platform: JSON.parse(request.postData() ?? "{}").platform,
        external_resource_id: externalResourceId,
        status: "active",
        granted_scopes: discordGrantedScopes("granted"),
      };
      state.connections = [connection];
      state.auditEvents.push(
        auditEvent("platform_connection.register", "platform_connection", connectionId),
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
        granted_scopes: discordGrantedScopes("requires_reauthorization"),
      };
      state.connections = [updated];
      state.auditEvents.push(
        auditEvent("platform_connection.revoke", "platform_connection", connectionId),
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
