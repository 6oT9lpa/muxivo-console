import { readonly, ref } from "vue";
import { consoleApi } from "../../api/consoleApi";
import type { Platform } from "../platforms/usePlatformAdapters";

export type ServerStatsSummary = {
  total_messages: number;
  active_users: number;
  active_channels: number;
  daily_active_users: number;
  weekly_active_users: number;
  monthly_active_users: number;
  messages_per_active_user: number;
  voice_users: number;
  total_voice_minutes: number;
  joins: number;
  leaves: number;
  joins_24h: number;
  joins_7d: number;
  joins_30d: number;
  leaves_24h: number;
  leaves_7d: number;
  leaves_30d: number;
  net_member_growth: number;
  current_member_count: number;
  moderation_events: number;
  membership_history_since: string | null;
  membership_history_complete: boolean;
  period_days: number;
};

export type ServerChannelStats = {
  channel_id: string;
  channel_name: string;
  messages: number;
};

export type ServerHourlyStats = {
  hour: number;
  count: number;
};

export type ServerDailyStats = {
  date: string;
  count: number;
};

export type PlatformServerStats = {
  organization_id: string;
  connection_id: string;
  platform: Platform;
  summary: ServerStatsSummary;
  channels: ServerChannelStats[];
  hourly: ServerHourlyStats[];
  daily: ServerDailyStats[];
};

export type ServerStatsState = "idle" | "loading" | "ready" | "unavailable";

export interface ServerStatsGateway {
  get(
    organizationId: string,
    connectionId: string,
    periodDays: number,
  ): Promise<PlatformServerStats>;
}

export class ConsoleServerStatsGateway implements ServerStatsGateway {
  async get(
    organizationId: string,
    connectionId: string,
    periodDays: number,
  ): Promise<PlatformServerStats> {
    const query = new URLSearchParams({ period: String(periodDays) });
    return consoleApi<PlatformServerStats>(
      `/api/v1/organizations/${encodeURIComponent(organizationId)}/platform-connections/${encodeURIComponent(connectionId)}/server-stats?${query.toString()}`,
    );
  }
}

export function useServerStats(gateway: ServerStatsGateway = new ConsoleServerStatsGateway()) {
  const state = ref<ServerStatsState>("idle");
  const stats = ref<PlatformServerStats | null>(null);
  let generation = 0;
  let activeOrganizationId = "";
  let activeConnectionId = "";
  let activePeriodDays = 30;

  async function load(
    organizationId: string,
    connectionId: string,
    periodDays = 30,
  ): Promise<ServerStatsState> {
    const requestGeneration = ++generation;
    resetState();
    activeOrganizationId = organizationId;
    activeConnectionId = connectionId;
    activePeriodDays = periodDays;
    if (!organizationId || !connectionId || !Number.isInteger(periodDays) || periodDays < 1 || periodDays > 365) {
      state.value = "unavailable";
      return state.value;
    }
    state.value = "loading";
    try {
      const response = await gateway.get(organizationId, connectionId, periodDays);
      if (!requestIsCurrent(requestGeneration, organizationId, connectionId)) return state.value;
      if (
        response.organization_id !== organizationId ||
        response.connection_id !== connectionId ||
        response.summary.period_days !== periodDays
      ) {
        throw new Error("Server stats response does not match the selected resource");
      }
      stats.value = response;
      state.value = "ready";
    } catch {
      if (!requestIsCurrent(requestGeneration, organizationId, connectionId)) return state.value;
      stats.value = null;
      state.value = "unavailable";
    }
    return state.value;
  }

  async function reload(): Promise<ServerStatsState> {
    if (!activeOrganizationId || !activeConnectionId) return state.value;
    return load(activeOrganizationId, activeConnectionId, activePeriodDays);
  }

  function clear(): void {
    generation += 1;
    activeOrganizationId = "";
    activeConnectionId = "";
    activePeriodDays = 30;
    resetState();
  }

  function requestIsCurrent(
    requestGeneration: number,
    organizationId: string,
    connectionId: string,
  ): boolean {
    return (
      requestGeneration === generation &&
      activeOrganizationId === organizationId &&
      activeConnectionId === connectionId
    );
  }

  function resetState(): void {
    state.value = "idle";
    stats.value = null;
  }

  return {
    state: readonly(state),
    stats: readonly(stats),
    load,
    reload,
    clear,
  };
}
