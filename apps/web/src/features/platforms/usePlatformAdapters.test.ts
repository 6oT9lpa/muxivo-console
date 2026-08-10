import { describe, expect, it } from "vitest";
import {
  type PlatformAdapterGateway,
  type PlatformAdapterList,
  usePlatformAdapters,
} from "./usePlatformAdapters";

class StubGateway implements PlatformAdapterGateway {
  constructor(private readonly result: PlatformAdapterList | Error) {}

  async list(): Promise<PlatformAdapterList> {
    if (this.result instanceof Error) throw this.result;
    return this.result;
  }
}

class DeferredGateway implements PlatformAdapterGateway {
  resolve: ((value: PlatformAdapterList) => void) | null = null;

  async list(): Promise<PlatformAdapterList> {
    return new Promise((resolve) => {
      this.resolve = resolve;
    });
  }
}

describe("usePlatformAdapters", () => {
  it("offers connection registration only for server-configured capabilities", async () => {
    const adapters = usePlatformAdapters(
      new StubGateway({
        items: [
          {
            platform: "discord",
            capabilities: ["connection_registration", "control_modules"],
          },
          { platform: "twitch", capabilities: ["control_modules"] },
        ],
      }),
    );

    const state = await adapters.load();

    expect(state).toBe("ready");
    expect(adapters.connectionPlatforms.value).toEqual(["discord"]);
    expect(adapters.supports("twitch", "connection_registration")).toBe(false);
  });

  it("fails closed instead of inventing future adapters", async () => {
    const adapters = usePlatformAdapters(new StubGateway(new Error("unavailable")));

    const state = await adapters.load();

    expect(state).toBe("unavailable");
    expect(adapters.connectionPlatforms.value).toEqual([]);
  });

  it("discards an in-flight capability response after logout", async () => {
    const gateway = new DeferredGateway();
    const adapters = usePlatformAdapters(gateway);
    const pending = adapters.load();

    adapters.clear();
    gateway.resolve?.({
      items: [{ platform: "discord", capabilities: ["connection_registration"] }],
    });
    await pending;

    expect(adapters.state.value).toBe("idle");
    expect(adapters.items.value).toEqual([]);
  });
});
