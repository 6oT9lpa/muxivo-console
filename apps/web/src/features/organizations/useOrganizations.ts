import { computed, readonly, ref } from "vue";
import { consoleApi } from "../../api/consoleApi";

export type OrganizationRole = "owner" | "admin" | "moderator" | "analyst" | "viewer";

export type OrganizationAccess = {
  id: string;
  name: string;
  slug: string;
  role: OrganizationRole;
};

export type OrganizationPage = {
  items: OrganizationAccess[];
  next_cursor: string | null;
};

export type OrganizationDirectoryState = "idle" | "loading" | "ready" | "empty" | "unavailable";

export interface OrganizationGateway {
  list(cursor?: string, limit?: number): Promise<OrganizationPage>;
}

export class ConsoleOrganizationGateway implements OrganizationGateway {
  async list(cursor?: string, limit = 50): Promise<OrganizationPage> {
    const query = new URLSearchParams({ limit: String(limit) });
    if (cursor) query.set("cursor", cursor);
    return consoleApi<OrganizationPage>(`/api/v1/organizations?${query.toString()}`);
  }
}

export function useOrganizations(
  gateway: OrganizationGateway = new ConsoleOrganizationGateway(),
) {
  const state = ref<OrganizationDirectoryState>("idle");
  const items = ref<OrganizationAccess[]>([]);
  const selectedId = ref("");
  const nextCursor = ref<string | null>(null);
  const loadingMore = ref(false);
  const selected = computed(
    () => items.value.find((organization) => organization.id === selectedId.value) ?? null,
  );
  let generation = 0;

  async function load(preferredId?: string): Promise<OrganizationDirectoryState> {
    const requestGeneration = ++generation;
    resetState();
    state.value = "loading";
    try {
      const page = await gateway.list(undefined, 50);
      if (requestGeneration !== generation) return state.value;
      items.value = page.items;
      nextCursor.value = page.next_cursor;
      const preferred = preferredId
        ? page.items.find((organization) => organization.id === preferredId)
        : undefined;
      selectedId.value = preferred?.id ?? page.items[0]?.id ?? "";
      state.value = page.items.length === 0 ? "empty" : "ready";
    } catch {
      if (requestGeneration !== generation) return state.value;
      state.value = "unavailable";
    }
    return state.value;
  }

  async function loadMore(): Promise<void> {
    if (!nextCursor.value || loadingMore.value) return;
    const requestGeneration = generation;
    const cursor = nextCursor.value;
    loadingMore.value = true;
    try {
      const page = await gateway.list(cursor, 50);
      if (requestGeneration !== generation) return;
      const knownIds = new Set(items.value.map((organization) => organization.id));
      items.value = [
        ...items.value,
        ...page.items.filter((organization) => !knownIds.has(organization.id)),
      ];
      nextCursor.value = page.next_cursor;
    } catch {
      // Preserve verified memberships and cursor so the user can retry.
    } finally {
      if (requestGeneration === generation) loadingMore.value = false;
    }
  }

  function select(organizationId: string): boolean {
    if (!items.value.some((organization) => organization.id === organizationId)) return false;
    selectedId.value = organizationId;
    return true;
  }

  function addAndSelect(organization: OrganizationAccess): void {
    generation += 1;
    items.value = [
      organization,
      ...items.value.filter((current) => current.id !== organization.id),
    ];
    selectedId.value = organization.id;
    state.value = "ready";
    loadingMore.value = false;
  }

  function clear(): void {
    generation += 1;
    resetState();
  }

  function resetState(): void {
    state.value = "idle";
    items.value = [];
    selectedId.value = "";
    nextCursor.value = null;
    loadingMore.value = false;
  }

  return {
    state: readonly(state),
    items: readonly(items),
    selectedId: readonly(selectedId),
    selected,
    nextCursor: readonly(nextCursor),
    loadingMore: readonly(loadingMore),
    load,
    loadMore,
    select,
    addAndSelect,
    clear,
  };
}
