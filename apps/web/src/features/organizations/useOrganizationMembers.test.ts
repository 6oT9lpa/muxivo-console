import { describe, expect, it } from "vitest";
import {
  type OrganizationMember,
  type OrganizationMemberGateway,
  type OrganizationMemberPage,
  useOrganizationMembers,
} from "./useOrganizationMembers";
import type { OrganizationRole } from "./useOrganizations";

const organizationA = "0198a6a2-7da7-7000-8000-000000000021";
const organizationB = "0198a6a2-7da7-7000-8000-000000000022";
const member: OrganizationMember = {
  membership_id: "0198a6a2-7da7-7000-8000-000000000031",
  user_id: "0198a6a2-7da7-7000-8000-000000000041",
  display_name: "Moderator",
  role: "moderator",
};

class StubGateway implements OrganizationMemberGateway {
  listCalls: Array<{ organizationId: string; cursor?: string; limit?: number }> = [];
  roleCalls: Array<{ organizationId: string; membershipId: string; role: OrganizationRole }> = [];

  constructor(
    private readonly pages: Array<OrganizationMemberPage | Error>,
    private readonly roleResults: Array<OrganizationMember | Error> = [],
  ) {}

  async list(
    organizationId: string,
    cursor?: string,
    limit?: number,
  ): Promise<OrganizationMemberPage> {
    this.listCalls.push({ organizationId, cursor, limit });
    const result = this.pages.shift();
    if (!result) throw new Error("No stub page");
    if (result instanceof Error) throw result;
    return result;
  }

  async updateRole(
    organizationId: string,
    membershipId: string,
    role: OrganizationRole,
  ): Promise<OrganizationMember> {
    this.roleCalls.push({ organizationId, membershipId, role });
    const result = this.roleResults.shift();
    if (!result) throw new Error("No stub role result");
    if (result instanceof Error) throw result;
    return result;
  }
}

class DeferredGateway implements OrganizationMemberGateway {
  listResolvers: Array<(value: OrganizationMemberPage) => void> = [];
  roleResolver: ((value: OrganizationMember) => void) | null = null;

  async list(): Promise<OrganizationMemberPage> {
    return new Promise((resolve) => this.listResolvers.push(resolve));
  }

  async updateRole(): Promise<OrganizationMember> {
    return new Promise((resolve) => {
      this.roleResolver = resolve;
    });
  }
}

describe("useOrganizationMembers", () => {
  it("loads a tenant-scoped roster and follows the server cursor", async () => {
    const second = { ...member, membership_id: "second-membership", display_name: "Viewer" };
    const gateway = new StubGateway([
      { items: [member], next_cursor: member.membership_id },
      { items: [member, second], next_cursor: null },
    ]);
    const roster = useOrganizationMembers(gateway);

    expect(await roster.load(organizationA)).toBe("ready");
    await roster.loadMore();

    expect(roster.items.value).toEqual([member, second]);
    expect(gateway.listCalls).toEqual([
      { organizationId: organizationA, cursor: undefined, limit: 50 },
      { organizationId: organizationA, cursor: member.membership_id, limit: 50 },
    ]);
  });

  it("discards a roster response after tenant scope changes", async () => {
    const gateway = new DeferredGateway();
    const roster = useOrganizationMembers(gateway);
    const firstLoad = roster.load(organizationA);
    const secondLoad = roster.load(organizationB);

    gateway.listResolvers[0]?.({ items: [member], next_cursor: null });
    await firstLoad;
    expect(roster.items.value).toEqual([]);

    gateway.listResolvers[1]?.({ items: [], next_cursor: null });
    await secondLoad;
    expect(roster.state.value).toBe("empty");
  });

  it("updates local role only after the server confirms the same membership", async () => {
    const updated = { ...member, role: "analyst" as const };
    const gateway = new StubGateway([{ items: [member], next_cursor: null }], [updated]);
    const roster = useOrganizationMembers(gateway);
    await roster.load(organizationA);

    expect(await roster.changeRole(member.membership_id, "analyst")).toBe(true);

    expect(roster.items.value[0]?.role).toBe("analyst");
    expect(gateway.roleCalls[0]).toEqual({
      organizationId: organizationA,
      membershipId: member.membership_id,
      role: "analyst",
    });
  });

  it("keeps the verified roster when a role mutation fails", async () => {
    const gateway = new StubGateway(
      [{ items: [member], next_cursor: null }],
      [new Error("forbidden")],
    );
    const roster = useOrganizationMembers(gateway);
    await roster.load(organizationA);

    expect(await roster.changeRole(member.membership_id, "viewer")).toBe(false);

    expect(roster.items.value).toEqual([member]);
    expect(roster.mutationFailed.value).toBe(true);
  });

  it("does not restore a role update after logout while the mutation is in flight", async () => {
    const gateway = new DeferredGateway();
    const roster = useOrganizationMembers(gateway);
    const load = roster.load(organizationA);
    gateway.listResolvers[0]?.({ items: [member], next_cursor: null });
    await load;

    const mutation = roster.changeRole(member.membership_id, "viewer");
    roster.clear();
    gateway.roleResolver?.({ ...member, role: "viewer" });
    await mutation;

    expect(roster.state.value).toBe("idle");
    expect(roster.items.value).toEqual([]);
    expect(roster.updatingMemberId.value).toBeNull();
  });
});
