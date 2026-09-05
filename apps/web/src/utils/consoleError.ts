import { ConsoleApiError } from "../api/consoleApi";

type Translator = (key: string) => string;

/** Maps API failures to neutral UI copy without leaking server details. */
export function consoleErrorMessage(error: unknown, t: Translator): string {
  if (error instanceof ConsoleApiError && error.status === 401) {
    return t("console.error.invalid_credentials");
  }
  if (error instanceof ConsoleApiError && error.status === 403) {
    return t("console.error.forbidden");
  }
  return t("console.error.unavailable");
}

