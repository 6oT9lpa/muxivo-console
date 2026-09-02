type PasswordChangeDraft = {
  currentPassword: string;
  newPassword: string;
  confirmNewPassword: string;
};

type PasswordRecoveryCompletionDraft = {
  token: string;
  newPassword: string;
  confirmNewPassword: string;
};

export function passwordChangeValidationMessage(draft: PasswordChangeDraft): string | null {
  if (!draft.currentPassword) return "Enter your current password.";
  if (draft.newPassword.length < 12) return "New password must be at least 12 characters.";
  if (draft.newPassword.length > 1024) return "New password is too long.";
  if (draft.newPassword !== draft.confirmNewPassword) return "New passwords do not match.";
  if (draft.currentPassword === draft.newPassword) {
    return "New password must be different from the current password.";
  }
  return null;
}

export function passwordRecoveryCompletionValidationMessage(
  draft: PasswordRecoveryCompletionDraft,
): string | null {
  if (!draft.token.trim()) return "Enter the recovery token.";
  if (/\s/.test(draft.token)) return "Recovery token must not contain spaces.";
  if (draft.newPassword.length < 12) return "New password must be at least 12 characters.";
  if (draft.newPassword.length > 1024) return "New password is too long.";
  if (draft.newPassword !== draft.confirmNewPassword) return "New passwords do not match.";
  return null;
}
