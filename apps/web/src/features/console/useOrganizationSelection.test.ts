import { ref } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { TranslationParams } from "../../i18n";

const { consoleApiMock } = vi.hoisted(() => ({
  consoleApiMock: vi.fn(),
}));

vi.mock("../../api/consoleApi", () => ({
  consoleApi: consoleApiMock,
}));

import { useOrganizationSelection } from "./useOrganizationSelection";

function createSelection() {
  const busy = ref(false);
  const notice = ref("");
  const refreshOrganizationWorkspace = vi.fn().mockResolvedValue(undefined);
  const resetOrganizationWorkspace = vi.fn();
  const selection = useOrganizationSelection({
    t: (key: string, params?: TranslationParams) =>
      params?.name ? `${key}:${params.name}` : key,
    busy,
    notice,
    messageFor: vi.fn().mockReturnValue("neutral error"),
    refreshOrganizationWorkspace,
    resetOrganizationWorkspace,
  });
  return {
    selection,
    busy,
    notice,
    refreshOrganizationWorkspace,
    resetOrganizationWorkspace,
  };
}

const organizationItem = (id: string, name = id) => ({
  organization: { id, name, slug: `${id}-slug` },
  membership: {
    id: `${id}-membership`,
    organization_id: id,
    user_id: "user-1",
    display_name: "Creator",
    role: "owner",
    resource_scopes: [],
  },
});

describe("useOrganizationSelection", () => {
  beforeEach(() => {
    consoleApiMock.mockReset();
  });

  it("selects the first available organization when the preferred one is stale", async () => {
    consoleApiMock.mockResolvedValue({
      items: [organizationItem("org-first"), organizationItem("org-second")],
    });
    const { selection, busy, refreshOrganizationWorkspace } = createSelection();

    await selection.loadOrganizations("deleted-org");

    expect(selection.selectedOrganizationId.value).toBe("org-first");
    expect(selection.activeOrganizationId.value).toBe("org-first");
    expect(selection.activeOrganization.value?.organization.slug).toBe("org-first-slug");
    expect(selection.organizationsLoaded.value).toBe(true);
    expect(refreshOrganizationWorkspace).toHaveBeenCalledOnce();
    expect(busy.value).toBe(false);
  });

  it("keeps the empty state when the user has no organizations", async () => {
    consoleApiMock.mockResolvedValue({ items: [] });
    const { selection, resetOrganizationWorkspace } = createSelection();

    await selection.loadOrganizations();

    expect(selection.organizations.value).toEqual([]);
    expect(selection.activeOrganization.value).toBeNull();
    expect(selection.activeOrganizationId.value).toBe("");
    expect(selection.organizationsLoaded.value).toBe(true);
    expect(resetOrganizationWorkspace).not.toHaveBeenCalled();
  });

  it("resets workspace and exposes a neutral error when loading fails", async () => {
    consoleApiMock.mockRejectedValue(new Error("database details must stay private"));
    const { selection, notice, resetOrganizationWorkspace } = createSelection();

    await selection.loadOrganizations();

    expect(selection.organizations.value).toEqual([]);
    expect(selection.selectedOrganizationId.value).toBe("");
    expect(notice.value).toBe("neutral error");
    expect(resetOrganizationWorkspace).toHaveBeenCalledOnce();
  });

  it("persists a changed active selection through workspace refresh", async () => {
    consoleApiMock.mockResolvedValue({
      items: [organizationItem("org-first"), organizationItem("org-second")],
    });
    const { selection, refreshOrganizationWorkspace } = createSelection();

    await selection.loadOrganizations("org-first");
    selection.selectedOrganizationId.value = "org-second";
    await selection.selectOrganization();

    expect(selection.activeOrganizationId.value).toBe("org-second");
    expect(refreshOrganizationWorkspace).toHaveBeenCalledTimes(2);
  });

  it("creates an organization and reloads it as the active selection", async () => {
    consoleApiMock
      .mockResolvedValueOnce({ id: "org-created", name: "Created", slug: "created" })
      .mockResolvedValueOnce({ items: [organizationItem("org-created", "Created")] });
    const { selection, notice } = createSelection();
    selection.organizationName.value = "Created";

    await selection.createOrganization();

    expect(consoleApiMock).toHaveBeenNthCalledWith(1, "/api/v1/organizations", {
      method: "POST",
      body: JSON.stringify({ name: "Created" }),
    });
    expect(selection.organizationName.value).toBe("");
    expect(selection.activeOrganizationId.value).toBe("org-created");
    expect(notice.value).toBe("console.notice.organization_ready:Created");
  });
});
