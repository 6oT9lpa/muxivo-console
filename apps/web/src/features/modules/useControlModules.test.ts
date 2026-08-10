import { describe, expect, it } from "vitest";
import {
  type ControlModuleGateway,
  type ControlModuleList,
  useControlModules,
} from "./useControlModules";

const organizationId = "0198a6a2-7da7-7000-8000-000000000021";

class StubGateway implements ControlModuleGateway {
  constructor(private readonly result: ControlModuleList | Error) {}

  async list(): Promise<ControlModuleList> {
    if (this.result instanceof Error) throw this.result;
    return this.result;
  }
}

class DeferredGateway implements ControlModuleGateway {
  resolve: ((value: ControlModuleList) => void) | null = null;

  async list(): Promise<ControlModuleList> {
    return new Promise((resolve) => {
      this.resolve = resolve;
    });
  }
}

describe("useControlModules", () => {
  it("loads platform-neutral modules returned for the selected tenant", async () => {
    const response: ControlModuleList = {
      organization_id: organizationId,
      items: [
        {
          key: "discord.dashboard-summary",
          display_name: "Dashboard summary",
          platform: "discord",
          capability: "view",
          status: "available",
        },
      ],
    };
    const catalog = useControlModules(new StubGateway(response));

    const state = await catalog.load(organizationId);

    expect(state).toBe("ready");
    expect(catalog.items.value).toEqual(response.items);
  });

  it("rejects a response projected for another organization", async () => {
    const catalog = useControlModules(
      new StubGateway({ organization_id: "different-tenant", items: [] }),
    );

    const state = await catalog.load(organizationId);

    expect(state).toBe("unavailable");
    expect(catalog.items.value).toEqual([]);
  });

  it("fails closed when the platform Control API is unavailable", async () => {
    const catalog = useControlModules(new StubGateway(new Error("control service unavailable")));

    const state = await catalog.load(organizationId);

    expect(state).toBe("unavailable");
    expect(catalog.items.value).toEqual([]);
  });

  it("discards an in-flight tenant response after scoped state is cleared", async () => {
    const gateway = new DeferredGateway();
    const catalog = useControlModules(gateway);
    const pending = catalog.load(organizationId);

    catalog.clear();
    gateway.resolve?.({
      organization_id: organizationId,
      items: [
        {
          key: "discord.health",
          display_name: "Platform health",
          platform: "discord",
          capability: "view",
          status: "available",
        },
      ],
    });
    await pending;

    expect(catalog.state.value).toBe("idle");
    expect(catalog.items.value).toEqual([]);
    expect(catalog.organizationId.value).toBe("");
  });
});
