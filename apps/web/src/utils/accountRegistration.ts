export type AccountRegistrationInput = {
  displayName: string;
  email: string;
  password: string;
};

export function accountRegistrationValidationMessage(
  input: AccountRegistrationInput,
): string | null {
  if (!input.displayName.trim()) return "Display name is required.";
  if (input.displayName.trim().length > 64) {
    return "Display name must be 64 characters or fewer.";
  }
  if (!input.email.trim()) return "Email is required.";
  if (input.password.length < 12) return "Password must be at least 12 characters.";
  if (input.password.length > 1024) return "Password must be 1024 characters or fewer.";
  return null;
}
