type LoginIdentityPresentation = {
  can_unlink: boolean;
};

type BrowserSessionAssurancePresentation = {
  assurance_level: "password" | "recent_authentication";
};

export function formatSecurityTimestamp(value: string | null): string {
  if (!value) return "Not available";
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return "Not available";
  return timestamp.toLocaleString();
}

export function loginIdentityProtectionMessage(identity: LoginIdentityPresentation): string {
  return identity.can_unlink
    ? "Can be unlinked with audit trail"
    : "Protected to keep account recovery usable";
}

export function loginIdentityActionLabel(identity: LoginIdentityPresentation): string {
  return identity.can_unlink ? "Unlink" : "Protected";
}

export function sessionBulkRevocationHelpMessage(
  currentSession: BrowserSessionAssurancePresentation | null,
): string {
  if (currentSession?.assurance_level === "recent_authentication") {
    return "Ready to revoke every active browser session.";
  }
  return "Refresh recent authentication before revoking every browser session.";
}
