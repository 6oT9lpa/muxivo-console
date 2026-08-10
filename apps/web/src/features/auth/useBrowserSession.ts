import { readonly, ref } from "vue";
import { consoleApi, ConsoleApiError } from "../../api/consoleApi";

export type BrowserSession = {
  user_id: string;
  session_id: string;
  assurance_level: "password" | "recent_authentication";
};

export type BrowserSessionState = "checking" | "authenticated" | "anonymous" | "unavailable";

export interface BrowserSessionGateway {
  current(): Promise<BrowserSession>;
}

export class ConsoleBrowserSessionGateway implements BrowserSessionGateway {
  async current(): Promise<BrowserSession> {
    return consoleApi<BrowserSession>("/api/v1/auth/sessions/current");
  }
}

export function useBrowserSession(
  gateway: BrowserSessionGateway = new ConsoleBrowserSessionGateway(),
) {
  const state = ref<BrowserSessionState>("checking");
  const session = ref<BrowserSession | null>(null);

  async function refresh(): Promise<BrowserSessionState> {
    state.value = "checking";
    try {
      session.value = await gateway.current();
      state.value = "authenticated";
    } catch (error) {
      session.value = null;
      state.value =
        error instanceof ConsoleApiError && error.status === 401 ? "anonymous" : "unavailable";
    }
    return state.value;
  }

  return {
    state: readonly(state),
    session: readonly(session),
    refresh,
  };
}
