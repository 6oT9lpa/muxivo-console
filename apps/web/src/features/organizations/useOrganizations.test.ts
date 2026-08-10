import { describe, expect, it } from "vitest";
import {
  type OrganizationAccess,
  type OrganizationGateway,
  type OrganizationPage,
  useOrganizations,
} from "./useOrganizations";

const first: OrganizationAccess = {
  id: "0198a6a2-7da7-7000-8000-000000000011",
  name: "Creator team",
  slug: "creator-team",
  role: "owner",
};
const second: OrganizationAccess = {
  id: "0198a6a2-7da7-7000-8000-000000000012",
  name: "Moderation team",
  slug: "moderation-team",
  role: "moderator",
};

class StubGateway implements OrganizationGateway {
  calls: Array<{ cursor?: string; limit?: number }> = [];

  constructor(private readonly pages: Array<OrganizationPage | Error>) {}

  async list(cursor?: string, limit?: number): Promise<OrganizationPage> {
    this.calls.push({ cursor, limit });
    const result = this.pages.shift();
    if (!result) throw new Error("No stub page");
    if (result instanceof Error) throw result;
    return result;
  }
}

class DeferredGateway implements OrganizationGateway {
  resolve: ((value: OrganizationPage) => void) | null = null;

  async list(): Promise<OrganizationPage> {
    return new Promise((resolve) => {
      this.resolve = resolve;
    });
  }
}

describe("useOrganizations", () => {
  it("loads only server-projected memberships and selects the first tenant", async () => {
    const directory = useOrganizations(
      new StubGateway([{ items: [first, second], next_cursor: null }]),
    );

    const state = await directory.load();

    expect(state).toBe("ready");
    expect(directory.items.value).toEqual([first, second]);
    expect(directory.selected.value).toEqual(first);
  });

  it("follows the server keyset cursor without duplicating tenants", async () => {
    const gateway = new StubGateway([
      { items: [first], next_cursor: first.id },
      { items: [first, second], next_cursor: null },
    ]);
    const directory = useOrganizations(gateway);
    await directory.load();

    await directory.loadMore();

    expect(directory.items.value).toEqual([first, second]);
    expect(directory.nextCursor.value).toBeNull();
    expect(gateway.calls[1]).toEqual({ cursor: first.id, limit: 50 });
  });

  it("does not allow a client-supplied organization outside the discovered set", async () => {
    const directory = useOrganizations(new StubGateway([{ items: [first], next_cursor: null }]));
    await directory.load();

    expect(directory.select("untrusted-organization-id")).toBe(false);
    expect(directory.selectedId.value).toBe(first.id);
  });

  it("fails closed when membership discovery is unavailable", async () => {
    const directory = useOrganizations(new StubGateway([new Error("network failure")]));

    const state = await directory.load();

    expect(state).toBe("unavailable");
    expect(directory.items.value).toEqual([]);
    expect(directory.selectedId.value).toBe("");
  });

  it("does not restore memberships after logout while a request is in flight", async () => {
    const gateway = new DeferredGateway();
    const directory = useOrganizations(gateway);
    const pending = directory.load();

    directory.clear();
    gateway.resolve?.({ items: [first], next_cursor: null });
    await pending;

    expect(directory.state.value).toBe("idle");
    expect(directory.items.value).toEqual([]);
    expect(directory.selectedId.value).toBe("");
  });
});
