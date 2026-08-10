import { describe, expect, it } from "vitest";
import { canAttemptAuditTimeline, formatAuditTimestamp } from "./auditPresentation";

describe("audit presentation", () => {
  it("only attempts audit reads for roles within the server's maximum capability", () => {
    expect(canAttemptAuditTimeline("owner")).toBe(true);
    expect(canAttemptAuditTimeline("admin")).toBe(true);
    expect(canAttemptAuditTimeline("analyst")).toBe(true);
    expect(canAttemptAuditTimeline("moderator")).toBe(false);
    expect(canAttemptAuditTimeline("viewer")).toBe(false);
  });

  it("preserves an invalid timestamp instead of inventing a date", () => {
    expect(formatAuditTimestamp("not-a-timestamp")).toBe("not-a-timestamp");
  });
});
