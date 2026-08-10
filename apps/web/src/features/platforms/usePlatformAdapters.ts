import { computed, readonly, ref } from "vue";
import { consoleApi } from "../../api/consoleApi";

export type Platform = "discord" | "twitch" | "telegram";
export type PlatformAdapterCapability =
  | "connection_registration"
  | "control_modules"
  | "health"
  | "dashboard_summary";

export type PlatformAdapter = {
  platform: Platform;
  capabilities: PlatformAdapterCapability[];
};

export type PlatformAdapterList = { items: PlatformAdapter[] };
export type PlatformAdapterState = "idle" | "loading" | "ready" | "empty" | "unavailable";

export interface PlatformAdapterGateway {
  list(): Promise<PlatformAdapterList>;
}

export class ConsolePlatformAdapterGateway implements PlatformAdapterGateway {
  async list(): Promise<PlatformAdapterList> {
    return consoleApi<PlatformAdapterList>("/api/v1/platform-adapters");
  }
}

export function usePlatformAdapters(
  gateway: PlatformAdapterGateway = new ConsolePlatformAdapterGateway(),
) {
  const state = ref<PlatformAdapterState>("idle");
  const items = ref<PlatformAdapter[]>([]);
  let generation = 0;

  const connectionPlatforms = computed(() =>
    items.value
      .filter((adapter) => adapter.capabilities.includes("connection_registration"))
      .map((adapter) => adapter.platform),
  );

  async function load(): Promise<PlatformAdapterState> {
    const requestGeneration = ++generation;
    resetState();
    state.value = "loading";
    try {
      const response = await gateway.list();
      if (requestGeneration !== generation) return state.value;
      items.value = response.items;
      state.value = response.items.length === 0 ? "empty" : "ready";
    } catch {
      if (requestGeneration !== generation) return state.value;
      items.value = [];
      state.value = "unavailable";
    }
    return state.value;
  }

  function supports(platform: Platform, capability: PlatformAdapterCapability): boolean {
    return (
      items.value.find((adapter) => adapter.platform === platform)?.capabilities.includes(capability) ??
      false
    );
  }

  function clear(): void {
    generation += 1;
    resetState();
  }

  function resetState(): void {
    state.value = "idle";
    items.value = [];
  }

  return {
    state: readonly(state),
    items: readonly(items),
    connectionPlatforms,
    load,
    supports,
    clear,
  };
}
