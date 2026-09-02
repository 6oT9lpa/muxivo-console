export type OrganizationRolePresentation = "owner" | "admin" | "moderator" | "analyst" | "viewer";

export type MembershipScopePresentation = {
  resource:
    | "console.control_modules"
    | "console.platform_connections"
    | "console.audit_events"
    | "console.organization_members";
  action: "read" | "manage";
};

export function roleSupportsMemberScope(
  role: OrganizationRolePresentation,
  scope: MembershipScopePresentation,
): boolean {
  if (scope.resource === "console.organization_members") {
    return role === "owner" || role === "admin";
  }
  if (scope.resource === "console.control_modules") {
    return scope.action === "read";
  }
  if (scope.resource === "console.platform_connections") {
    return role === "admin" && (scope.action === "read" || scope.action === "manage");
  }
  if (scope.resource === "console.audit_events") {
    return (role === "admin" || role === "analyst") && scope.action === "read";
  }
  return false;
}

export function supportedMemberScopesForRole<T extends MembershipScopePresentation>(
  role: OrganizationRolePresentation,
  scopes: T[],
): T[] {
  return scopes.filter((scope) => roleSupportsMemberScope(role, scope));
}
