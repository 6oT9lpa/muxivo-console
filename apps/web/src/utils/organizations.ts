export const ACTIVE_ORGANIZATION_STORAGE_KEY = "muxivo.console.activeOrganizationId";

export type OrganizationSelectionItem = {
  organization: {
    id: string;
  };
};

export function chooseActiveOrganizationId(
  organizations: OrganizationSelectionItem[],
  preferredOrganizationId: string,
): string {
  const preferred = preferredOrganizationId.trim();
  if (preferred && organizations.some((item) => item.organization.id === preferred)) {
    return preferred;
  }
  return organizations[0]?.organization.id ?? "";
}

export function persistActiveOrganizationId(storage: Storage, organizationId: string): void {
  if (organizationId) {
    storage.setItem(ACTIVE_ORGANIZATION_STORAGE_KEY, organizationId);
    return;
  }
  storage.removeItem(ACTIVE_ORGANIZATION_STORAGE_KEY);
}
