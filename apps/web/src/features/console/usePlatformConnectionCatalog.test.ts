import { computed, ref } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { TranslationParams } from "../../i18n";
import type { ConnectionWizardCopy } from "../../utils/connectionWizard";

const { consoleApiMock, ConsoleApiErrorMock } = vi.hoisted(() => ({
  consoleApiMock: vi.fn(),
  ConsoleApiErrorMock: class ConsoleApiErrorMock extends Error {
    constructor(readonly status: number, message = "Console request failed") {
      super(message);
    }
  },
}));

vi.mock("../../api/consoleApi", () => ({
  consoleApi: consoleApiMock,
  ConsoleApiError: ConsoleApiErrorMock,
}));

import { usePlatformConnectionCatalog } from "./usePlatformConnectionCatalog";

const wizardOptions: ConnectionWizardCopy[] = [
  {
    platform: "discord",
    title: "Connect Discord",
    summary: "summary",
    actionLabel: "Connect",
    candidateLabel: "Servers",
    candidateHelp: "Choose a server",
    preflightSteps: ["Verify"],
  },
  {
    platform: "twitch",
    title: "Connect Twitch",
    summary: "summary",
    actionLabel: "Connect",
    candidateLabel: "Channels",
    candidateHelp: "Choose a channel",
    preflightSteps: ["Verify"],
  },
];

const candidate = (id: string, displayName = id) => ({
  platform: "discord" as const,
  external_resource_id: id,
  display_name: displayName,
});

const connection = (id: string, status: "active" | "pending" | "disconnected" = "active") => ({
  id,
  organization_id: "org-1",
  platform: "discord" as const,
  external_resource_id: id,
  status,
  status_reason: null,
  granted_scopes: [],
});

function createCatalog() {
  const activeOrganizationId = ref("org-1");
  const canReadPlatformConnections = ref(true);
  const canManagePlatformConnections = ref(true);
  const busy = ref(false);
  const notice = ref("");
  const catalog = usePlatformConnectionCatalog({
    t: (key: string, params?: TranslationParams) =>
      params?.platform || params?.status ? `${key}:${params.platform ?? params.status}` : key,
    busy,
    notice,
    messageFor: vi.fn().mockReturnValue("neutral error"),
    activeOrganizationId: computed(() => activeOrganizationId.value),
    canReadPlatformConnections: computed(() => canReadPlatformConnections.value),
    canManagePlatformConnections: computed(() => canManagePlatformConnections.value),
    localizedConnectionWizardOptions: computed(() => wizardOptions),
    platformLabel: (platform) => platform,
    connectionStatusLabel: (status) => status,
  });
  return {
    catalog,
    activeOrganizationId,
    canReadPlatformConnections,
    canManagePlatformConnections,
    busy,
    notice,
  };
}

describe("usePlatformConnectionCatalog", () => {
  beforeEach(() => {
    consoleApiMock.mockReset();
  });

  it("loads only browser-safe candidates that are not already connected", async () => {
    consoleApiMock.mockResolvedValue({
      identity_linked: true,
      platform: "discord",
      items: [candidate("already-connected"), candidate("available")],
    });
    const { catalog } = createCatalog();
    catalog.connections.value = [connection("already-connected")];

    await catalog.loadConnectionCandidates();

    expect(catalog.selectableConnectionCandidates.value).toEqual([candidate("available")]);
    expect(catalog.selectedConnectionCandidateId.value).toBe("available");
    expect(consoleApiMock).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/platform-connection-candidates?platform=discord",
    );
  });

  it("fails closed when the active organization cannot manage connections", async () => {
    const { catalog, canManagePlatformConnections } = createCatalog();
    canManagePlatformConnections.value = false;
    catalog.connectionCandidates.value = [candidate("stale")];

    await catalog.loadConnectionCandidates();

    expect(consoleApiMock).not.toHaveBeenCalled();
    expect(catalog.connectionCandidates.value).toEqual([]);
    expect(catalog.selectedConnectionCandidateId.value).toBe("");
  });

  it("connects only the selected server-advertised candidate", async () => {
    consoleApiMock.mockResolvedValue(connection("server-1", "pending"));
    const { catalog } = createCatalog();
    catalog.connectionCandidates.value = [candidate("server-1", "Muxivo")];
    catalog.selectedConnectionCandidateId.value = "server-1";

    await catalog.connectPlatform();

    expect(consoleApiMock).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/platform-connections",
      {
        method: "POST",
        body: JSON.stringify({
          platform: "discord",
          external_resource_id: "server-1",
        }),
      },
    );
    expect(catalog.connections.value[0]?.status).toBe("pending");
    expect(catalog.selectedConnectionId.value).toBe("server-1");
    expect(catalog.selectedConnectionCandidateId.value).toBe("");
  });

  it("sends a stable idempotency key for lifecycle actions", async () => {
    consoleApiMock.mockResolvedValue(connection("connection-1", "disconnected"));
    const { catalog } = createCatalog();

    const completed = await catalog.runConnectionLifecycle(connection("connection-1"), "disconnect");

    expect(consoleApiMock).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/platform-connections/connection-1",
      {
        method: "DELETE",
        headers: { "Idempotency-Key": "disconnect:connection-1" },
      },
    );
    expect(completed).toBe(true);
  });

  it("keeps a 503 candidate catalog failure retryable without leaking details", async () => {
    consoleApiMock.mockRejectedValue(new ConsoleApiErrorMock(503, "private upstream detail"));
    const { catalog, notice } = createCatalog();

    await catalog.loadConnectionCandidates();

    expect(catalog.connectionCandidatesUnavailable.value).toBe(true);
    expect(notice.value).toBe("");
  });
});
