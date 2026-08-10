import { readonly, ref } from "vue";
import { consoleApi } from "../../api/consoleApi";

export type DashboardSummary = {
  organization_id: string;
  connection_id: string;
  platform: "discord" | "twitch" | "telegram";
  messages_today: number;
  ai_flagged_today: number;
  creator_sources: number;
  bot_latency_ms: number | null;
};

export type DashboardSummaryState = "idle" | "loading" | "ready" | "unavailable";

export interface DashboardSummaryGateway {
  get(organizationId: string, connectionId: string): Promise<DashboardSummary>;
}

export class ConsoleDashboardSummaryGateway implements DashboardSummaryGateway {
  async get(organizationId: string, connectionId: string): Promise<DashboardSummary> {
    return consoleApi<DashboardSummary>(
      `/api/v1/organizations/${encodeURIComponent(organizationId)}/platform-connections/${encodeURIComponent(connectionId)}/dashboard-summary`,
    );
  }
}

export function useDashboardSummary(
  gateway: DashboardSummaryGateway = new ConsoleDashboardSummaryGateway(),
) {
  const state = ref<DashboardSummaryState>("idle");
  const summary = ref<DashboardSummary | null>(null);
  let generation = 0;

  async function load(
    organizationId: string,
    connectionId: string,
  ): Promise<DashboardSummaryState> {
    const requestGeneration = ++generation;
    resetState();
    if (!organizationId || !connectionId) return state.value;
    state.value = "loading";
    try {
      const response = await gateway.get(organizationId, connectionId);
      if (requestGeneration !== generation) return state.value;
      if (
        response.organization_id !== organizationId ||
        response.connection_id !== connectionId
      ) {
        throw new Error("Dashboard response does not match the selected resource");
      }
      summary.value = response;
      state.value = "ready";
    } catch {
      if (requestGeneration !== generation) return state.value;
      summary.value = null;
      state.value = "unavailable";
    }
    return state.value;
  }

  function clear(): void {
    generation += 1;
    resetState();
  }

  function resetState(): void {
    state.value = "idle";
    summary.value = null;
  }

  return {
    state: readonly(state),
    summary: readonly(summary),
    load,
    clear,
  };
}
