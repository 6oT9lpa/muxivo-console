import { describe, expect, it } from "vitest";

import { isDiscordActivityAuthLaunch } from "./authLaunchContext";

describe("auth launch context", () => {
  it("recognizes Console opened from Discord Activity", () => {
    expect(isDiscordActivityAuthLaunch(new URL("https://muxivo.pro/?source=discord-activity"))).toBe(true);
  });

  it("does not trust unrelated or missing launch markers", () => {
    expect(isDiscordActivityAuthLaunch(new URL("https://muxivo.pro/?source=twitch"))).toBe(false);
    expect(isDiscordActivityAuthLaunch(new URL("https://muxivo.pro/"))).toBe(false);
    expect(isDiscordActivityAuthLaunch(null)).toBe(false);
  });
});
