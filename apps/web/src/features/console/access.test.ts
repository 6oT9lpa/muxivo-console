import { describe, expect, it } from "vitest";

import {
  canEditOrganizationMember,
  canManageOrganizationMembers,
  memberHasScope,
  memberRoleOptionsForActor,
  membershipAllows,
  scopesEqual,
  supportedScopesForRole,
} from "./access";

const platformRead = {
  resource: "console.platform_connections" as const,
  action: "read" as const,
};

describe("organization access policy", () => {
  it("grants owners every organization permission", () => {
    expect(
      membershipAllows(
        { role: "owner", resource_scopes: [] },
        "console.organization_members",
        "manage",
      ),
    ).toBe(true);
  });

  it("requires an explicit scope for non-owner members", () => {
    expect(
      membershipAllows(
        { role: "analyst", resource_scopes: [platformRead] },
        "console.platform_connections",
        "read",
      ),
    ).toBe(true);
    expect(
      membershipAllows(
        { role: "analyst", resource_scopes: [platformRead] },
        "console.platform_connections",
        "manage",
      ),
    ).toBe(false);
    expect(membershipAllows(null, platformRead.resource, platformRead.action)).toBe(false);
  });

  it("keeps role assignment below the current actor", () => {
    expect(memberRoleOptionsForActor("owner")).toEqual([
      "admin",
      "moderator",
      "analyst",
      "viewer",
    ]);
    expect(memberRoleOptionsForActor("admin")).toEqual([
      "moderator",
      "analyst",
      "viewer",
    ]);
    expect(canEditOrganizationMember("admin", "owner")).toBe(false);
    expect(canEditOrganizationMember("admin", "admin")).toBe(false);
    expect(canEditOrganizationMember("admin", "moderator")).toBe(true);
  });

  it("compares scopes independently of persistence ids", () => {
    expect(scopesEqual(platformRead, { ...platformRead, id: "scope-1" })).toBe(true);
    expect(
      memberHasScope(
        { resource_scopes: [{ ...platformRead, id: "scope-1" }] },
        platformRead,
      ),
    ).toBe(true);
  });

  it("filters scopes that the selected role cannot use", () => {
    expect(
      supportedScopesForRole("admin", [
        platformRead,
        { resource: "console.platform_connections", action: "manage" },
        { resource: "console.audit_events", action: "read" },
      ]),
    ).toEqual([
      platformRead,
      { resource: "console.platform_connections", action: "manage" },
      { resource: "console.audit_events", action: "read" },
    ]);
  });

  it("recognizes only admins and owners as member managers", () => {
    expect(canManageOrganizationMembers("owner")).toBe(true);
    expect(canManageOrganizationMembers("admin")).toBe(true);
    expect(canManageOrganizationMembers("analyst")).toBe(false);
    expect(canManageOrganizationMembers(undefined)).toBe(false);
  });
});
