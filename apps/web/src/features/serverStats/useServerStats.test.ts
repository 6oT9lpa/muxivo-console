import { describe, expect, it } from "vitest";
import {
  type PlatformServerStats,
  type ServerStatsGateway,
  useServerStats,
} from "./useServerStats";

const organizationId = "0198a6a2-7da7-7000-8000-000000000061";
const connectionId = "0198a6a2-7da7-7000-8000-000000000062";

function response(overrides: Partial<PlatformServerStats> = {}): PlatformServerStats {
  return {
    organization_id: organizationId,
    connection_id: connectionId,
    platform: "discord",
    summary: {
      total_messages: 120,
      active_users: 20,
      active_channels: 4,
      daily_active_users: 8,
      weekly_active_users: 15,
      monthly_active_users: 20,
      messages_per_active_user: 6,
      voice_users: 5,
      total_voice_minutes: 300,
      joins: 12,
      leaves: 2,
      joins_24h: 1,
      joins_7d: 4,
      joins_30d: 12,
      leaves_24h: 0,
      leaves_7d: 1,
      leaves_30d: 2,
      net_member_growth: 10,
      current_member_count: 450,
      moderation_events: 7,
      membership_history_since: null,
      membership_history_complete: false,
      period_days: 30,
    },
    channels: [{ channel_id: "123", channel_name: "general", messages: 80 }],
    hourly: [{ hour: 12, count: 11 }],
    daily: [{ date: "2026-08-10", count: 22 }],
    ...overrides,
  };
}

class StubGateway implements ServerStatsGateway {
  calls: Array<{ organizationId: string; connectionId: string; periodDays: number }> = [];

  constructor(private readonly result: PlatformServerStats | Error) {}

  async get(
    targetOrganizationId: string,
    targetConnectionId: string,
    periodDays: number,
  ): Promise<PlatformServerStats> {
    this.calls.push({
      organizationId: targetOrganizationId,
      connectionId: targetConnectionId,
      periodDays,
    });
    if (this.result instanceof Error) throw this.result;
    return this.result;
  }
}

class DeferredGateway implements ServerStatsGateway {
  resolve: ((value: PlatformServerStats) => void) | null = null;

  async get(): Promise<PlatformServerStats> {
    return new Promise((resolve) => {
      this.resolve = resolve;
    });
  }
}

describe("useServerStats", () => {
  it("loads the selected connection and period", async () => {
    const gateway = new StubGateway(response());
    const serverStats = useServerStats(gateway);

    const state = await serverStats.load(organizationId, connectionId, 30);

    expect(state).toBe("ready");
    expect(serverStats.stats.value?.summary.total_messages).toBe(120);
    expect(gateway.calls).toEqual([{ organizationId, connectionId, periodDays: 30 }]);
  });

  it("fails closed when the response belongs to another resource", async () => {
    const serverStats = useServerStats(
      new StubGateway(response({ connection_id: "another-connection" })),
    );

    const state = await serverStats.load(organizationId, connectionId, 30);

    expect(state).toBe("unavailable");
    expect(serverStats.stats.value).toBeNull();
  });

  it("fails closed when the returned period differs from the request", async () => {
    const mismatched = response();
    mismatched.summary = { ...mismatched.summary, period_days: 7 };
    const serverStats = useServerStats(new StubGateway(mismatched));

    const state = await serverStats.load(organizationId, connectionId, 30);

    expect(state).toBe("unavailable");
    expect(serverStats.stats.value).toBeNull();
  });

  it("does not restore stale stats after the workspace is cleared", async () => {
    const gateway = new DeferredGateway();
    const serverStats = useServerStats(gateway);
    const pending = serverStats.load(organizationId, connectionId, 30);

    serverStats.clear();
    gateway.resolve?.(response());
    await pending;

    expect(serverStats.state.value).toBe("idle");
    expect(serverStats.stats.value).toBeNull();
  });

  it("rejects an invalid period before calling the gateway", async () => {
    const gateway = new StubGateway(response());
    const serverStats = useServerStats(gateway);

    const state = await serverStats.load(organizationId, connectionId, 366);

    expect(state).toBe("unavailable");
    expect(gateway.calls).toEqual([]);
  });
});
