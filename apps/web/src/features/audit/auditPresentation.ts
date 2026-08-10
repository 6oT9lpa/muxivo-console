import type { OrganizationRole } from "../organizations/useOrganizations";

export function canAttemptAuditTimeline(role: OrganizationRole): boolean {
  return role === "owner" || role === "admin" || role === "analyst";
}

export function formatAuditTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}
