import { describe, expect, it } from "vitest";
import {
  connectionWizardFor,
  connectionWizardOptions,
  type ConnectablePlatform,
} from "./connectionWizard";

describe("connection wizard copy", () => {
  it("exposes only production-supported foundation connection choices", () => {
    expect(connectionWizardOptions.map((option) => option.platform)).toEqual([
      "discord",
      "twitch",
    ]);
  });

  it.each([
    ["discord", "Connect Discord server", "Discord server ID", "Discord"],
    ["twitch", "Connect Twitch channel", "Twitch channel ID", "Twitch"],
  ] satisfies [ConnectablePlatform, string, string, string][])(
    "describes the %s product wizard instead of a raw resource form",
    (platform, title, resourceLabel, ownershipKeyword) => {
      const copy = connectionWizardFor(platform);

      expect(copy.title).toBe(title);
      expect(copy.resourceLabel).toBe(resourceLabel);
      expect(copy.preflightSteps).toContain(
        `Link the matching ${ownershipKeyword} identity.`,
      );
      expect(copy.preflightSteps.join(" ")).toContain("Control API");
      expect(copy.preflightSteps.join(" ")).toContain("non-secret");
      expect(copy.preflightSteps.join(" ")).toContain("audit event");
    },
  );
});
