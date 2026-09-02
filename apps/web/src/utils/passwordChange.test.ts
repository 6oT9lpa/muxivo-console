import { describe, expect, it } from "vitest";
import {
  passwordChangeValidationMessage,
  passwordRecoveryCompletionValidationMessage,
} from "./passwordChange";

describe("password change validation", () => {
  it("requires the current password", () => {
    expect(
      passwordChangeValidationMessage({
        currentPassword: "",
        newPassword: "a-strong-new-password",
        confirmNewPassword: "a-strong-new-password",
      }),
    ).toBe("Enter your current password.");
  });

  it("requires a production-length new password", () => {
    expect(
      passwordChangeValidationMessage({
        currentPassword: "current-password",
        newPassword: "short",
        confirmNewPassword: "short",
      }),
    ).toBe("New password must be at least 12 characters.");
  });

  it("requires matching confirmation", () => {
    expect(
      passwordChangeValidationMessage({
        currentPassword: "current-password",
        newPassword: "a-strong-new-password",
        confirmNewPassword: "another-strong-password",
      }),
    ).toBe("New passwords do not match.");
  });

  it("rejects a no-op password rotation", () => {
    expect(
      passwordChangeValidationMessage({
        currentPassword: "same-password",
        newPassword: "same-password",
        confirmNewPassword: "same-password",
      }),
    ).toBe("New password must be different from the current password.");
  });

  it("accepts a valid draft", () => {
    expect(
      passwordChangeValidationMessage({
        currentPassword: "current-password",
        newPassword: "a-strong-new-password",
        confirmNewPassword: "a-strong-new-password",
      }),
    ).toBeNull();
  });

  it("validates recovery completion token and password confirmation", () => {
    expect(
      passwordRecoveryCompletionValidationMessage({
        token: "",
        newPassword: "a-strong-new-password",
        confirmNewPassword: "a-strong-new-password",
      }),
    ).toBe("Enter the recovery token.");
    expect(
      passwordRecoveryCompletionValidationMessage({
        token: "bad token",
        newPassword: "a-strong-new-password",
        confirmNewPassword: "a-strong-new-password",
      }),
    ).toBe("Recovery token must not contain spaces.");
    expect(
      passwordRecoveryCompletionValidationMessage({
        token: "opaque-token",
        newPassword: "a-strong-new-password",
        confirmNewPassword: "different-strong-password",
      }),
    ).toBe("New passwords do not match.");
    expect(
      passwordRecoveryCompletionValidationMessage({
        token: "opaque-token",
        newPassword: "a-strong-new-password",
        confirmNewPassword: "a-strong-new-password",
      }),
    ).toBeNull();
  });
});
