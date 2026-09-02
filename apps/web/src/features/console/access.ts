import type {
  AuthorizationAction,
  AuthorizationResource,
  MembershipScopeInput,
  OrganizationMembership,
  OrganizationRole,
} from "./types";

import { supportedMemberScopesForRole } from "../../utils/memberScopes";

export const MEMBER_ROLE_OPTIONS: readonly OrganizationRole[] = [
  "admin",
  "moderator",
  "analyst",
  "viewer",
];

export const DEFAULT_MEMBER_SCOPE_OPTIONS: MembershipScopeInput[] = [
  { resource: "console.control_modules", action: "read" },
  { resource: "console.platform_connections", action: "read" },
  { resource: "console.platform_connections", action: "manage" },
  { resource: "console.audit_events", action: "read" },
  { resource: "console.organization_members", action: "manage" },
];

/** Returns whether a membership can perform the requested organization action. */
export function membershipAllows(
  membership: Pick<OrganizationMembership, "role" | "resource_scopes"> | null | undefined,
  resource: AuthorizationResource,
  action: AuthorizationAction,
): boolean {
  if (!membership) return false;
  if (membership.role === "owner") return true;
  return membership.resource_scopes.some(
    (scope) => scope.resource === resource && scope.action === action,
  );
}

/** Keeps the member-management boundary aligned with the backend role hierarchy. */
export function canManageOrganizationMembers(role: OrganizationRole | null | undefined): boolean {
  return role === "owner" || role === "admin";
}

/** Limits role assignment to roles that the current actor is allowed to grant. */
export function memberRoleOptionsForActor(
  actorRole: OrganizationRole | null | undefined,
): OrganizationRole[] {
  return actorRole === "owner"
    ? [...MEMBER_ROLE_OPTIONS]
    : ["moderator", "analyst", "viewer"];
}

/** Prevents editing owners and prevents non-owners from escalating a member. */
export function canEditOrganizationMember(
  actorRole: OrganizationRole | null | undefined,
  memberRole: OrganizationRole,
): boolean {
  if (memberRole === "owner") return false;
  if (actorRole === "owner") return true;
  return ["moderator", "analyst", "viewer"].includes(memberRole);
}

/** Compares scopes by policy identity and deliberately ignores persistence ids. */
export function scopesEqual(left: MembershipScopeInput, right: MembershipScopeInput): boolean {
  return left.resource === right.resource && left.action === right.action;
}

export function memberHasScope(
  member: Pick<OrganizationMembership, "resource_scopes">,
  scope: MembershipScopeInput,
): boolean {
  return member.resource_scopes.some((item) => scopesEqual(item, scope));
}

export function supportedScopesForRole<T extends MembershipScopeInput>(
  role: OrganizationRole,
  scopes: T[],
): T[] {
  return supportedMemberScopesForRole(role, scopes);
}
