import { describe, expect, it } from "vitest";
import {
  type DashboardSummary,
  type DashboardSummaryGateway,
  useDashboardSummary,
} from "./useDashboardSummary";

const organizationId = "0198a6a2-7da7-7000-8000-000000000031";
const connectionId = "0198a6a2-7da7-7000-8000-000000000032";
const summary: DashboardSummary = {
  organization_id: organizationId,
  connection_id: connectionId,
  platform: "discord",
  messages_today: 1200,
  ai_flagged_today: 14,
  creator_sources: 4,
  bot_latency_ms: 38,
};

class StubGateway implements DashboardSummaryGateway {
  constructor(private readonly result: DashboardSummary | Error) {}

  async get(): Promise<DashboardSummary> {
    if (this.result instanceof Error) throw this.result;
    return this.result;
  }
}

class DeferredGateway implements DashboardSummaryGateway {
  resolve: ((value: DashboardSummary) => void) | null = null;

  async get(): Promise<DashboardSummary> {
    return new Promise((resolve) => {
      this.resolve = resolve;
    });
  }
}

describe("useDashboardSummary", () => {
  it("exposes a resource-bound dashboard projection", async () => {
    const dashboard = useDashboardSummary(new StubGateway(summary));

    const state = await dashboard.load(organizationId, connectionId);

    expect(state).toBe("ready");
    expect(dashboard.summary.value).toEqual(summary);
  });

  it("rejects a summary bound to another connection", async () => {
    const dashboard = useDashboardSummary(
      new StubGateway({ ...summary, connection_id: "different-connection" }),
    );

    const state = await dashboard.load(organizationId, connectionId);

    expect(state).toBe("unavailable");
    expect(dashboard.summary.value).toBeNull();
  });

  it("fails closed when the Control API cannot provide the module", async () => {
    const dashboard = useDashboardSummary(new StubGateway(new Error("unavailable")));

    const state = await dashboard.load(organizationId, connectionId);

    expect(state).toBe("unavailable");
    expect(dashboard.summary.value).toBeNull();
  });

  it("discards an in-flight summary after tenant state is cleared", async () => {
    const gateway = new DeferredGateway();
    const dashboard = useDashboardSummary(gateway);
    const pending = dashboard.load(organizationId, connectionId);

    dashboard.clear();
    gateway.resolve?.(summary);
    await pending;

    expect(dashboard.state.value).toBe("idle");
    expect(dashboard.summary.value).toBeNull();
  });
});
