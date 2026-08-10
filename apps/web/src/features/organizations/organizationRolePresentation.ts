import type { OrganizationRole } from "./useOrganizations";

const roleRank: Record<OrganizationRole, number> = {
  owner: 0,
  admin: 1,
  moderator: 2,
  analyst: 3,
  viewer: 4,
};

const assignableRoles: OrganizationRole[] = ["admin", "moderator", "analyst", "viewer"];

export function assignableMemberRoles(
  actorRole: OrganizationRole,
  targetRole: OrganizationRole,
): OrganizationRole[] {
  if (targetRole === "owner" || (actorRole !== "owner" && actorRole !== "admin")) return [];
  if (roleRank[actorRole] >= roleRank[targetRole]) return [];
  return assignableRoles.filter((role) => roleRank[actorRole] < roleRank[role]);
}
