import { describe, expect, it } from "vitest";
import { assignableMemberRoles } from "./organizationRolePresentation";

describe("assignableMemberRoles", () => {
  it("lets owners manage every non-owner role", () => {
    expect(assignableMemberRoles("owner", "admin")).toEqual([
      "admin",
      "moderator",
      "analyst",
      "viewer",
    ]);
  });

  it("lets admins manage only roles below admin", () => {
    expect(assignableMemberRoles("admin", "moderator")).toEqual([
      "moderator",
      "analyst",
      "viewer",
    ]);
  });

  it("does not present equal, higher or owner mutations", () => {
    expect(assignableMemberRoles("admin", "admin")).toEqual([]);
    expect(assignableMemberRoles("owner", "owner")).toEqual([]);
    expect(assignableMemberRoles("moderator", "viewer")).toEqual([]);
  });
});
