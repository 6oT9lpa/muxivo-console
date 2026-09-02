import { describe, expect, it } from "vitest";
import {
  formatSecurityTimestamp,
  loginIdentityActionLabel,
  loginIdentityProtectionMessage,
  sessionBulkRevocationHelpMessage,
} from "./securityPresentation";

describe("security presentation helpers", () => {
  it("formats empty or invalid timestamps as unavailable", () => {
    expect(formatSecurityTimestamp(null)).toBe("Not available");
    expect(formatSecurityTimestamp("not-a-date")).toBe("Not available");
  });

  it("keeps valid timestamps presentable", () => {
    expect(formatSecurityTimestamp("2026-08-09T00:00:00Z")).not.toBe("Not available");
  });

  it("explains whether a login identity can be unlinked", () => {
    expect(loginIdentityProtectionMessage({ can_unlink: true })).toBe(
      "Can be unlinked with audit trail",
    );
    expect(loginIdentityProtectionMessage({ can_unlink: false })).toBe(
      "Protected to keep account recovery usable",
    );
  });

  it("labels login identity actions without exposing backend details", () => {
    expect(loginIdentityActionLabel({ can_unlink: true })).toBe("Unlink");
    expect(loginIdentityActionLabel({ can_unlink: false })).toBe("Protected");
  });

  it("explains the recent-auth gate for bulk session revocation", () => {
    expect(sessionBulkRevocationHelpMessage(null)).toBe(
      "Refresh recent authentication before revoking every browser session.",
    );
    expect(sessionBulkRevocationHelpMessage({ assurance_level: "password" })).toBe(
      "Refresh recent authentication before revoking every browser session.",
    );
    expect(sessionBulkRevocationHelpMessage({ assurance_level: "recent_authentication" })).toBe(
      "Ready to revoke every active browser session.",
    );
  });
});
