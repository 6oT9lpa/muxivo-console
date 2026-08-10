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

  async function load(preferredId?: string): Promise<OrganizationDirectoryState> {
    state.value = "loading";
    items.value = [];
    selectedId.value = "";
    nextCursor.value = null;
    try {
      const page = await gateway.list(undefined, 50);
      items.value = page.items;
      nextCursor.value = page.next_cursor;
      const preferred = preferredId
        ? page.items.find((organization) => organization.id === preferredId)
        : undefined;
      selectedId.value = preferred?.id ?? page.items[0]?.id ?? "";
      state.value = page.items.length === 0 ? "empty" : "ready";
    } catch {
      state.value = "unavailable";
    }
    return state.value;
  }

  async function loadMore(): Promise<void> {
    if (!nextCursor.value || loadingMore.value) return;
    loadingMore.value = true;
    try {
      const page = await gateway.list(nextCursor.value, 50);
      const knownIds = new Set(items.value.map((organization) => organization.id));
      items.value = [
        ...items.value,
        ...page.items.filter((organization) => !knownIds.has(organization.id)),
      ];
      nextCursor.value = page.next_cursor;
    } catch {
      // Preserve the already verified tenant set and cursor so the user can retry safely.
    } finally {
      loadingMore.value = false;
    }
  }

  function select(organizationId: string): boolean {
    if (!items.value.some((organization) => organization.id === organizationId)) return false;
    selectedId.value = organizationId;
    return true;
  }

  function addAndSelect(organization: OrganizationAccess): void {
    items.value = [
      organization,
      ...items.value.filter((current) => current.id !== organization.id),
    ];
    selectedId.value = organization.id;
    state.value = "ready";
  }

  function clear(): void {
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
