import { describe, expect, it, vi } from "vitest";

import { chooseActiveOrganizationId, persistActiveOrganizationId } from "./organizations";

const organizations = [
  { organization: { id: "org-owner" } },
  { organization: { id: "org-viewer" } },
];

describe("chooseActiveOrganizationId", () => {
  it("keeps the stored organization when it still belongs to the user", () => {
    expect(chooseActiveOrganizationId(organizations, "org-viewer")).toBe("org-viewer");
  });

  it("falls back to the first available organization when the stored one is stale", () => {
    expect(chooseActiveOrganizationId(organizations, "deleted-org")).toBe("org-owner");
  });

  it("returns an empty selection for the first-organization empty state", () => {
    expect(chooseActiveOrganizationId([], "deleted-org")).toBe("");
  });
});

describe("persistActiveOrganizationId", () => {
  it("stores the active organization id", () => {
    const storage = {
      setItem: vi.fn(),
      removeItem: vi.fn(),
    } as unknown as Storage;

    persistActiveOrganizationId(storage, "org-owner");

    expect(storage.setItem).toHaveBeenCalledWith(
      "muxivo.console.activeOrganizationId",
      "org-owner",
    );
    expect(storage.removeItem).not.toHaveBeenCalled();
  });

  it("removes the local selection for the empty state", () => {
    const storage = {
      setItem: vi.fn(),
      removeItem: vi.fn(),
    } as unknown as Storage;

    persistActiveOrganizationId(storage, "");

    expect(storage.removeItem).toHaveBeenCalledWith("muxivo.console.activeOrganizationId");
    expect(storage.setItem).not.toHaveBeenCalled();
  });
});
