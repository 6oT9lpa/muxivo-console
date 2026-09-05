import { computed, ref } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { TranslationParams } from "../../i18n";

const { consoleApiMock } = vi.hoisted(() => ({
  consoleApiMock: vi.fn(),
}));

vi.mock("../../api/consoleApi", () => ({
  consoleApi: consoleApiMock,
}));

import { useOrganizationMembers } from "./useOrganizationMembers";

function member(userId = "user-1") {
  return {
    id: `${userId}-membership`,
    organization_id: "org-1",
    user_id: userId,
    display_name: "Member",
    role: "viewer" as const,
    resource_scopes: [
      { id: "scope-1", resource: "console.control_modules" as const, action: "read" as const },
    ],
  };
}

function invitation() {
  return {
    id: "invitation-1",
    organization_id: "org-1",
    email_hint: "m***@example.com",
    role: "viewer" as const,
    resource_scopes: [],
    status: "pending" as const,
    expires_at: "2030-01-01T00:00:00Z",
    created_at: "2029-01-01T00:00:00Z",
    accepted_at: null,
    revoked_at: null,
    delivery_status: "sent" as const,
  };
}

function createMembers(actorRole: "owner" | "admin" | "moderator" | "analyst" | "viewer" = "owner") {
  const activeOrganizationId = ref("org-1");
  const actorRoleRef = ref(actorRole);
  const busy = ref(false);
  const notice = ref("");
  const messageFor = vi.fn().mockReturnValue("neutral error");
  const members = useOrganizationMembers({
    t: (key: string, params?: TranslationParams) =>
      params?.count === undefined ? key : `${key}:${params.count}`,
    busy,
    notice,
    messageFor,
    activeOrganizationId: computed(() => activeOrganizationId.value),
    actorRole: computed(() => actorRoleRef.value),
  });
  return { members, busy, notice, messageFor, activeOrganizationId, actorRoleRef };
}

describe("useOrganizationMembers", () => {
  beforeEach(() => {
    consoleApiMock.mockReset();
  });

  it("loads members and invitations only for a manageable organization", async () => {
    consoleApiMock
      .mockResolvedValueOnce({ items: [member()] })
      .mockResolvedValueOnce({ items: [invitation()] });
    const { members } = createMembers("admin");

    await members.loadOrganizationMembers();
    await members.loadOrganizationInvitations();

    expect(members.organizationMembers.value).toHaveLength(1);
    expect(members.organizationInvitations.value).toHaveLength(1);
    expect(consoleApiMock).toHaveBeenNthCalledWith(
      1,
      "/api/v1/organizations/org-1/members",
    );
    expect(consoleApiMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/organizations/org-1/member-invitations",
    );
  });

  it("fails closed for a role that cannot manage members", async () => {
    const { members } = createMembers("viewer");

    await members.loadOrganizationMembers();
    await members.loadOrganizationInvitations();

    expect(consoleApiMock).not.toHaveBeenCalled();
    expect(members.organizationMembers.value).toEqual([]);
    expect(members.organizationInvitations.value).toEqual([]);
    expect(members.canManageOrganizationMembers.value).toBe(false);
  });

  it("trims the invitation email and resets the form after creation", async () => {
    consoleApiMock.mockResolvedValue(invitation());
    const { members, notice } = createMembers();
    members.newMemberEmail.value = "  member@example.com  ";
    members.newMemberRole.value = "viewer";

    await members.addOrganizationMember();

    expect(consoleApiMock).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/member-invitations",
      {
        method: "POST",
        body: JSON.stringify({
          email: "member@example.com",
          role: "viewer",
          resource_scopes: [{ resource: "console.control_modules", action: "read" }],
        }),
      },
    );
    expect(members.organizationInvitations.value).toEqual([invitation()]);
    expect(members.newMemberEmail.value).toBe("");
    expect(members.newMemberRole.value).toBe("viewer");
    expect(notice.value).toBe("console.notice.member_invited");
  });

  it("updates and removes members through the active organization boundary", async () => {
    const updated = { ...member(), display_name: "Updated" };
    consoleApiMock.mockResolvedValueOnce(updated).mockResolvedValueOnce(undefined);
    const { members } = createMembers();
    members.organizationMembers.value = [member()];

    await members.saveOrganizationMember(member());
    expect(members.organizationMembers.value).toEqual([updated]);

    await members.removeOrganizationMember(updated);
    expect(members.organizationMembers.value).toEqual([]);
    expect(consoleApiMock).toHaveBeenLastCalledWith(
      "/api/v1/organizations/org-1/members/user-1",
      { method: "DELETE" },
    );
  });

  it("uses a neutral notice when an organization member request fails", async () => {
    consoleApiMock.mockRejectedValue(new Error("backend details must stay private"));
    const { members, notice, messageFor } = createMembers();
    members.newMemberEmail.value = "member@example.com";

    await members.addOrganizationMember();

    expect(messageFor).toHaveBeenCalledOnce();
    expect(notice.value).toBe("neutral error");
  });
});
