import { describe, expect, it } from "vitest";
import { accountRegistrationValidationMessage } from "./accountRegistration";

describe("account registration validation", () => {
  const validInput = {
    displayName: "Creator",
    email: "creator@example.com",
    password: "a-long-enough-password",
  };

  it("accepts a complete Foundation account registration", () => {
    expect(accountRegistrationValidationMessage(validInput)).toBeNull();
  });

  it("requires a display name", () => {
    expect(
      accountRegistrationValidationMessage({ ...validInput, displayName: "   " }),
    ).toBe("Display name is required.");
  });

  it("matches the backend password length contract", () => {
    expect(accountRegistrationValidationMessage({ ...validInput, password: "short" })).toBe(
      "Password must be at least 12 characters.",
    );
    expect(
      accountRegistrationValidationMessage({ ...validInput, password: "x".repeat(1025) }),
    ).toBe("Password must be 1024 characters or fewer.");
  });
});
