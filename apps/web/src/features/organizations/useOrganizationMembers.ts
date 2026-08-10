import { readonly, ref } from "vue";
import { consoleApi } from "../../api/consoleApi";
import type { OrganizationRole } from "./useOrganizations";

export type OrganizationMember = {
  membership_id: string;
  user_id: string;
  display_name: string;
  role: OrganizationRole;
};

export type OrganizationMemberPage = {
  items: OrganizationMember[];
  next_cursor: string | null;
};

export type OrganizationMemberState = "idle" | "loading" | "ready" | "empty" | "unavailable";

export interface OrganizationMemberGateway {
  list(organizationId: string, cursor?: string, limit?: number): Promise<OrganizationMemberPage>;
  updateRole(
    organizationId: string,
    membershipId: string,
    role: OrganizationRole,
  ): Promise<OrganizationMember>;
}

export class ConsoleOrganizationMemberGateway implements OrganizationMemberGateway {
  async list(
    organizationId: string,
    cursor?: string,
    limit = 50,
  ): Promise<OrganizationMemberPage> {
    const query = new URLSearchParams({ limit: String(limit) });
    if (cursor) query.set("cursor", cursor);
    return consoleApi<OrganizationMemberPage>(
      `/api/v1/organizations/${encodeURIComponent(organizationId)}/members?${query.toString()}`,
    );
  }

  async updateRole(
    organizationId: string,
    membershipId: string,
    role: OrganizationRole,
  ): Promise<OrganizationMember> {
    return consoleApi<OrganizationMember>(
      `/api/v1/organizations/${encodeURIComponent(organizationId)}/members/${encodeURIComponent(membershipId)}/role`,
      { method: "PATCH", body: JSON.stringify({ role }) },
    );
  }
}

export function useOrganizationMembers(
  gateway: OrganizationMemberGateway = new ConsoleOrganizationMemberGateway(),
) {
  const state = ref<OrganizationMemberState>("idle");
  const items = ref<OrganizationMember[]>([]);
  const nextCursor = ref<string | null>(null);
  const loadingMore = ref(false);
  const updatingMemberId = ref<string | null>(null);
  const mutationFailed = ref(false);
  let generation = 0;
  let activeOrganizationId = "";

  async function load(organizationId: string): Promise<OrganizationMemberState> {
    const requestGeneration = ++generation;
    resetState();
    activeOrganizationId = organizationId;
    if (!organizationId) return state.value;
    state.value = "loading";
    try {
      const page = await gateway.list(organizationId, undefined, 50);
      if (requestGeneration !== generation || activeOrganizationId !== organizationId) {
        return state.value;
      }
      items.value = page.items;
      nextCursor.value = page.next_cursor;
      state.value = page.items.length === 0 ? "empty" : "ready";
    } catch {
      if (requestGeneration !== generation || activeOrganizationId !== organizationId) {
        return state.value;
      }
      state.value = "unavailable";
    }
    return state.value;
  }

  async function loadMore(): Promise<void> {
    if (!activeOrganizationId || !nextCursor.value || loadingMore.value) return;
    const requestGeneration = generation;
    const organizationId = activeOrganizationId;
    const cursor = nextCursor.value;
    loadingMore.value = true;
    try {
      const page = await gateway.list(organizationId, cursor, 50);
      if (requestGeneration !== generation || activeOrganizationId !== organizationId) return;
      const knownIds = new Set(items.value.map((member) => member.membership_id));
      items.value = [
        ...items.value,
        ...page.items.filter((member) => !knownIds.has(member.membership_id)),
      ];
      nextCursor.value = page.next_cursor;
    } catch {
      // Preserve the verified roster and cursor so the operator can retry.
    } finally {
      if (requestGeneration === generation && activeOrganizationId === organizationId) {
        loadingMore.value = false;
      }
    }
  }

  async function changeRole(membershipId: string, role: OrganizationRole): Promise<boolean> {
    const current = items.value.find((member) => member.membership_id === membershipId);
    if (!current || !activeOrganizationId || updatingMemberId.value) return false;
    if (current.role === role) return true;

    const requestGeneration = generation;
    const organizationId = activeOrganizationId;
    mutationFailed.value = false;
    updatingMemberId.value = membershipId;
    try {
      const updated = await gateway.updateRole(organizationId, membershipId, role);
      if (requestGeneration !== generation || activeOrganizationId !== organizationId) return false;
      if (updated.membership_id !== membershipId || updated.user_id !== current.user_id) {
        throw new Error("Role response does not match the selected membership");
      }
      items.value = items.value.map((member) =>
        member.membership_id === membershipId ? updated : member,
      );
      return true;
    } catch {
      if (requestGeneration === generation && activeOrganizationId === organizationId) {
        mutationFailed.value = true;
      }
      return false;
    } finally {
      if (requestGeneration === generation && activeOrganizationId === organizationId) {
        updatingMemberId.value = null;
      }
    }
  }

  function clear(): void {
    generation += 1;
    activeOrganizationId = "";
    resetState();
  }

  function resetState(): void {
    state.value = "idle";
    items.value = [];
    nextCursor.value = null;
    loadingMore.value = false;
    updatingMemberId.value = null;
    mutationFailed.value = false;
  }

  return {
    state: readonly(state),
    items: readonly(items),
    nextCursor: readonly(nextCursor),
    loadingMore: readonly(loadingMore),
    updatingMemberId: readonly(updatingMemberId),
    mutationFailed: readonly(mutationFailed),
    load,
    loadMore,
    changeRole,
    clear,
  };
}
