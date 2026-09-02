export type ConsoleTheme = "dark" | "light";

export const CONSOLE_THEME_STORAGE_KEY = "muxivo-console.theme";

type ThemeStorage = Pick<Storage, "getItem" | "setItem">;

export function readConsoleTheme(storage: ThemeStorage | null): ConsoleTheme {
  try {
    return storage?.getItem(CONSOLE_THEME_STORAGE_KEY) === "light" ? "light" : "dark";
  } catch {
    // A blocked browser storage must not prevent the Console from rendering.
    return "dark";
  }
}

export function persistConsoleTheme(storage: ThemeStorage | null, theme: ConsoleTheme): void {
  try {
    storage?.setItem(CONSOLE_THEME_STORAGE_KEY, theme);
  } catch {
    // The in-memory theme remains usable when persistence is unavailable.
  }
}

export function nextConsoleTheme(theme: ConsoleTheme): ConsoleTheme {
  return theme === "dark" ? "light" : "dark";
}
