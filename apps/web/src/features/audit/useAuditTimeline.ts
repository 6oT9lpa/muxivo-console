import { readonly, ref } from "vue";
import { consoleApi, ConsoleApiError } from "../../api/consoleApi";

export type AuditResult = "allowed" | "denied" | "succeeded" | "failed";

export type AuditEntry = {
  id: string;
  correlation_id: string;
  actor_id: string | null;
  organization_id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  result: AuditResult;
  created_at: string;
};

export type AuditPage = {
  items: AuditEntry[];
  next_cursor: string | null;
};

export type AuditFilters = {
  actorId?: string;
  action?: string;
  resourceType?: string;
  result?: AuditResult;
};

export type AuditTimelineState =
  | "idle"
  | "loading"
  | "ready"
  | "empty"
  | "denied"
  | "unavailable";

export interface AuditTimelineGateway {
  list(
    organizationId: string,
    cursor: string | undefined,
    filters: AuditFilters,
    limit?: number,
  ): Promise<AuditPage>;
}

export class ConsoleAuditTimelineGateway implements AuditTimelineGateway {
  async list(
    organizationId: string,
    cursor: string | undefined,
    filters: AuditFilters,
    limit = 50,
  ): Promise<AuditPage> {
    const query = new URLSearchParams({ limit: String(limit) });
    if (cursor) query.set("cursor", cursor);
    if (filters.actorId) query.set("actor_id", filters.actorId);
    if (filters.action) query.set("action", filters.action);
    if (filters.resourceType) query.set("resource_type", filters.resourceType);
    if (filters.result) query.set("result", filters.result);
    return consoleApi<AuditPage>(
      `/api/v1/organizations/${encodeURIComponent(organizationId)}/audit-events?${query.toString()}`,
    );
  }
}

export function useAuditTimeline(
  gateway: AuditTimelineGateway = new ConsoleAuditTimelineGateway(),
) {
  const state = ref<AuditTimelineState>("idle");
  const items = ref<AuditEntry[]>([]);
  const nextCursor = ref<string | null>(null);
  const loadingMore = ref(false);
  const filters = ref<AuditFilters>({});
  let generation = 0;
  let activeOrganizationId = "";

  async function load(
    organizationId: string,
    requestedFilters: AuditFilters = {},
  ): Promise<AuditTimelineState> {
    const requestGeneration = ++generation;
    resetState();
    activeOrganizationId = organizationId;
    filters.value = normalizeFilters(requestedFilters);
    if (!organizationId) return state.value;
    state.value = "loading";
    try {
      const page = await gateway.list(organizationId, undefined, filters.value, 50);
      if (!requestIsCurrent(requestGeneration, organizationId)) return state.value;
      requireTenant(page, organizationId);
      items.value = page.items;
      nextCursor.value = page.next_cursor;
      state.value = page.items.length === 0 ? "empty" : "ready";
    } catch (error) {
      if (!requestIsCurrent(requestGeneration, organizationId)) return state.value;
      failClosed(error);
    }
    return state.value;
  }

  async function reload(): Promise<AuditTimelineState> {
    if (!activeOrganizationId) return state.value;
    return load(activeOrganizationId, filters.value);
  }

  async function loadMore(): Promise<void> {
    if (!activeOrganizationId || !nextCursor.value || loadingMore.value) return;
    const requestGeneration = generation;
    const organizationId = activeOrganizationId;
    const cursor = nextCursor.value;
    loadingMore.value = true;
    try {
      const page = await gateway.list(organizationId, cursor, filters.value, 50);
      if (!requestIsCurrent(requestGeneration, organizationId)) return;
      requireTenant(page, organizationId);
      const knownIds = new Set(items.value.map((entry) => entry.id));
      items.value = [
        ...items.value,
        ...page.items.filter((entry) => !knownIds.has(entry.id)),
      ];
      nextCursor.value = page.next_cursor;
    } catch (error) {
      if (requestIsCurrent(requestGeneration, organizationId)) failClosed(error);
    } finally {
      if (requestIsCurrent(requestGeneration, organizationId)) loadingMore.value = false;
    }
  }

  function clear(): void {
    generation += 1;
    activeOrganizationId = "";
    filters.value = {};
    resetState();
  }

  function requestIsCurrent(requestGeneration: number, organizationId: string): boolean {
    return requestGeneration === generation && activeOrganizationId === organizationId;
  }

  function failClosed(error: unknown): void {
    items.value = [];
    nextCursor.value = null;
    loadingMore.value = false;
    state.value = error instanceof ConsoleApiError && error.status === 403 ? "denied" : "unavailable";
  }

  function resetState(): void {
    state.value = "idle";
    items.value = [];
    nextCursor.value = null;
    loadingMore.value = false;
  }

  return {
    state: readonly(state),
    items: readonly(items),
    nextCursor: readonly(nextCursor),
    loadingMore: readonly(loadingMore),
    filters: readonly(filters),
    load,
    reload,
    loadMore,
    clear,
  };
}

function normalizeFilters(filters: AuditFilters): AuditFilters {
  const normalized: AuditFilters = {};
  const actorId = filters.actorId?.trim();
  const action = filters.action?.trim();
  const resourceType = filters.resourceType?.trim();
  if (actorId) normalized.actorId = actorId;
  if (action) normalized.action = action;
  if (resourceType) normalized.resourceType = resourceType;
  if (filters.result) normalized.result = filters.result;
  return normalized;
}

function requireTenant(page: AuditPage, organizationId: string): void {
  if (page.items.some((entry) => entry.organization_id !== organizationId)) {
    throw new Error("Audit response does not match the selected organization");
  }
}
