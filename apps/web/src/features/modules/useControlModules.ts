import { readonly, ref } from "vue";
import { consoleApi } from "../../api/consoleApi";

export type ControlModule = {
  key: string;
  display_name: string;
  platform: "discord" | "twitch" | "telegram";
  capability: "view" | "manage";
  status: "available" | "unavailable" | "requires_reauthorization";
};

export type ControlModuleList = {
  organization_id: string;
  items: ControlModule[];
};

export type ControlModuleState = "idle" | "loading" | "ready" | "empty" | "unavailable";

export interface ControlModuleGateway {
  list(organizationId: string): Promise<ControlModuleList>;
}

export class ConsoleControlModuleGateway implements ControlModuleGateway {
  async list(organizationId: string): Promise<ControlModuleList> {
    return consoleApi<ControlModuleList>(
      `/api/v1/organizations/${encodeURIComponent(organizationId)}/control-modules`,
    );
  }
}

export function useControlModules(
  gateway: ControlModuleGateway = new ConsoleControlModuleGateway(),
) {
  const state = ref<ControlModuleState>("idle");
  const items = ref<ControlModule[]>([]);
  const organizationId = ref("");

  async function load(targetOrganizationId: string): Promise<ControlModuleState> {
    clear();
    if (!targetOrganizationId) return state.value;
    organizationId.value = targetOrganizationId;
    state.value = "loading";
    try {
      const response = await gateway.list(targetOrganizationId);
      if (response.organization_id !== targetOrganizationId) {
        throw new Error("Control module response belongs to a different organization");
      }
      items.value = response.items;
      state.value = response.items.length === 0 ? "empty" : "ready";
    } catch {
      items.value = [];
      state.value = "unavailable";
    }
    return state.value;
  }

  function clear(): void {
    state.value = "idle";
    items.value = [];
    organizationId.value = "";
  }

  return {
    state: readonly(state),
    items: readonly(items),
    organizationId: readonly(organizationId),
    load,
    clear,
  };
}
