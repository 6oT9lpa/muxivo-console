import { describe, expect, it, vi } from "vitest";

import {
  CONSOLE_THEME_STORAGE_KEY,
  nextConsoleTheme,
  persistConsoleTheme,
  readConsoleTheme,
} from "./theme";

describe("Console theme state", () => {
  it("defaults to dark for a missing or invalid stored value", () => {
    const storage = { getItem: vi.fn().mockReturnValue("sepia") } as unknown as Storage;

    expect(readConsoleTheme(storage)).toBe("dark");
    expect(storage.getItem).toHaveBeenCalledWith(CONSOLE_THEME_STORAGE_KEY);
  });

  it("restores a light theme from browser storage", () => {
    const storage = { getItem: vi.fn().mockReturnValue("light") } as unknown as Storage;

    expect(readConsoleTheme(storage)).toBe("light");
  });

  it("persists the selected theme without exposing other application state", () => {
    const storage = { setItem: vi.fn() } as unknown as Storage;

    persistConsoleTheme(storage, "light");

    expect(storage.setItem).toHaveBeenCalledWith(CONSOLE_THEME_STORAGE_KEY, "light");
  });

  it.each([
    ["dark", "light"],
    ["light", "dark"],
  ] as const)("toggles %s to %s", (current, expected) => {
    expect(nextConsoleTheme(current)).toBe(expected);
  });
});
