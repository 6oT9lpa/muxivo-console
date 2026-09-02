import { clientLogger } from "../utils/clientLogger";

const csrfCookieName =
  import.meta.env.VITE_CONSOLE_CSRF_COOKIE_NAME ?? "__Host-muxivo_csrf";

export class ConsoleApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

function csrfToken(): string | undefined {
  return document.cookie
    .split("; ")
    .find((cookie) => cookie.startsWith(`${csrfCookieName}=`))
    ?.split("=", 2)[1];
}

export async function consoleApi<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = csrfToken();
    if (token) headers.set("X-CSRF-Token", token);
  }
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const requestPath = path.split("?", 1)[0];
  clientLogger.info("api.request.started", { method, path: requestPath });
  try {
    const response = await fetch(`${import.meta.env.VITE_CONSOLE_API_BASE ?? ""}${path}`, {
      ...init,
      headers,
      credentials: "include",
    });
    clientLogger.info("api.request.completed", {
      method,
      path: requestPath,
      status: response.status,
    });
    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as { detail?: string } | null;
      throw new ConsoleApiError(response.status, body?.detail ?? "Console request failed");
    }
    return (response.status === 204 ? undefined : response.json()) as T;
  } catch (error) {
    clientLogger.error("api.request.failed", {
      method,
      path: requestPath,
      error_type: error instanceof Error ? error.constructor.name : "UnknownError",
    });
    throw error;
  }
}
