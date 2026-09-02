import { describe, expect, it } from "vitest";
import { roleSupportsMemberScope, supportedMemberScopesForRole } from "./memberScopes";

const platformManage = {
  resource: "console.platform_connections" as const,
  action: "manage" as const,
};
const auditRead = {
  resource: "console.audit_events" as const,
  action: "read" as const,
};
const controlRead = {
  resource: "console.control_modules" as const,
  action: "read" as const,
};
const memberManage = {
  resource: "console.organization_members" as const,
  action: "manage" as const,
};

describe("member scope role policy", () => {
  it("allows admin operational scopes", () => {
    expect(roleSupportsMemberScope("admin", platformManage)).toBe(true);
    expect(roleSupportsMemberScope("admin", memberManage)).toBe(true);
    expect(roleSupportsMemberScope("admin", auditRead)).toBe(true);
  });

  it("keeps viewer/moderator scopes narrow", () => {
    expect(roleSupportsMemberScope("viewer", controlRead)).toBe(true);
    expect(roleSupportsMemberScope("viewer", platformManage)).toBe(false);
    expect(roleSupportsMemberScope("moderator", platformManage)).toBe(false);
  });

  it("keeps analyst read-only for audit plus common control visibility", () => {
    expect(supportedMemberScopesForRole("analyst", [
      platformManage,
      auditRead,
      controlRead,
      memberManage,
    ])).toEqual([auditRead, controlRead]);
  });
});
