import { computed, ref, type ComputedRef, type Ref } from "vue";

import { consoleApi } from "../../api/consoleApi";
import type { TranslationParams } from "../../i18n";
import { clientLogger } from "../../utils/clientLogger";
import {
  DEFAULT_MEMBER_SCOPE_OPTIONS,
  canManageOrganizationMembers,
  memberRoleOptionsForActor,
  supportedScopesForRole,
} from "./access";
import type {
  MembershipScopeInput,
  OrganizationInvitation,
  OrganizationMembership,
  OrganizationRole,
} from "./types";

type Translate = (key: string, params?: TranslationParams) => string;

type OrganizationMembersDependencies = {
  t: Translate;
  busy: Ref<boolean>;
  notice: Ref<string>;
  messageFor: (error: unknown) => string;
  activeOrganizationId: ComputedRef<string>;
  actorRole: ComputedRef<OrganizationRole | undefined>;
};

/** Coordinates organization member management without leaking it into the app shell. */
export function useOrganizationMembers(
  dependencies: OrganizationMembersDependencies,
) {
  const {
    t,
    busy,
    notice,
    messageFor,
    activeOrganizationId,
    actorRole,
  } = dependencies;

  const organizationMembers = ref<OrganizationMembership[]>([]);
  const organizationInvitations = ref<OrganizationInvitation[]>([]);
  const newMemberEmail = ref("");
  const newMemberRole = ref<OrganizationRole>("viewer");
  const newMemberScopes = ref<MembershipScopeInput[]>([
    { resource: "console.control_modules", action: "read" },
  ]);
  const canManageMembers = computed(() => canManageOrganizationMembers(actorRole.value));
  const availableMemberRoleOptions = computed<OrganizationRole[]>(() =>
    memberRoleOptionsForActor(actorRole.value),
  );
  const memberScopeOptions: MembershipScopeInput[] = DEFAULT_MEMBER_SCOPE_OPTIONS.map(
    (scope) => ({ ...scope }),
  );
  const availableNewMemberScopeOptions = computed(() =>
    supportedScopesForRole(newMemberRole.value, memberScopeOptions),
  );

  async function loadOrganizationMembers(): Promise<void> {
    if (!activeOrganizationId.value || !canManageMembers.value) {
      organizationMembers.value = [];
      clientLogger.info("console.organization.members.load_skipped", {
        has_active_organization: Boolean(activeOrganizationId.value),
      });
      return;
    }
    busy.value = true;
    notice.value = "";
    clientLogger.info("console.organization.members.load_requested");
    try {
      const payload = await consoleApi<{ items: OrganizationMembership[] }>(
        `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/members`,
      );
      organizationMembers.value = payload.items;
      clientLogger.info("console.organization.members.loaded", {
        count: payload.items.length,
      });
    } catch (error) {
      organizationMembers.value = [];
      notice.value = messageFor(error);
      clientLogger.warn("console.organization.members.load_failed", {
        error_type: error instanceof Error ? error.name : "unknown",
      });
    } finally {
      busy.value = false;
    }
  }

  async function loadOrganizationInvitations(): Promise<void> {
    if (!activeOrganizationId.value || !canManageMembers.value) {
      organizationInvitations.value = [];
      clientLogger.info("console.organization.invitations.load_skipped", {
        has_active_organization: Boolean(activeOrganizationId.value),
      });
      return;
    }
    busy.value = true;
    notice.value = "";
    clientLogger.info("console.organization.invitations.load_requested");
    try {
      const payload = await consoleApi<{ items: OrganizationInvitation[] }>(
        `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/member-invitations`,
      );
      organizationInvitations.value = payload.items;
      clientLogger.info("console.organization.invitations.loaded", {
        count: payload.items.length,
      });
    } catch (error) {
      organizationInvitations.value = [];
      notice.value = messageFor(error);
      clientLogger.warn("console.organization.invitations.load_failed", {
        error_type: error instanceof Error ? error.name : "unknown",
      });
    } finally {
      busy.value = false;
    }
  }

  async function addOrganizationMember(): Promise<void> {
    const email = newMemberEmail.value.trim();
    if (!activeOrganizationId.value || !email || !canManageMembers.value) return;
    normalizeNewMemberScopes();
    busy.value = true;
    notice.value = "";
    clientLogger.info("console.organization.invitation.create_requested");
    try {
      const invitation = await consoleApi<OrganizationInvitation>(
        `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/member-invitations`,
        {
          method: "POST",
          body: JSON.stringify({
            email,
            role: newMemberRole.value,
            resource_scopes: newMemberScopes.value,
          }),
        },
      );
      organizationInvitations.value = [invitation, ...organizationInvitations.value];
      resetInvitationForm();
      notice.value =
        invitation.delivery_status === "sent"
          ? t("console.notice.member_invited")
          : t("console.notice.member_invitation_delivery_unavailable");
      clientLogger.info("console.organization.invitation.create_completed", {
        delivery_status: invitation.delivery_status ?? "unknown",
      });
    } catch (error) {
      notice.value = messageFor(error);
      clientLogger.warn("console.organization.invitation.create_failed", {
        error_type: error instanceof Error ? error.name : "unknown",
      });
    } finally {
      busy.value = false;
    }
  }

  async function revokeOrganizationInvitation(
    invitation: OrganizationInvitation,
  ): Promise<void> {
    if (
      !activeOrganizationId.value ||
      !canManageMembers.value ||
      invitation.status !== "pending"
    ) {
      return;
    }
    busy.value = true;
    notice.value = "";
    clientLogger.info("console.organization.invitation.revoke_requested");
    try {
      await consoleApi<void>(
        `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/member-invitations/${encodeURIComponent(invitation.id)}`,
        { method: "DELETE" },
      );
      organizationInvitations.value = organizationInvitations.value.map((current) =>
        current.id === invitation.id
          ? { ...current, status: "revoked", revoked_at: new Date().toISOString() }
          : current,
      );
      notice.value = t("console.notice.member_invitation_revoked");
      clientLogger.info("console.organization.invitation.revoke_completed");
    } catch (error) {
      notice.value = messageFor(error);
      clientLogger.warn("console.organization.invitation.revoke_failed", {
        error_type: error instanceof Error ? error.name : "unknown",
      });
    } finally {
      busy.value = false;
    }
  }

  async function saveOrganizationMember(member: OrganizationMembership): Promise<void> {
    if (!activeOrganizationId.value || !canManageMembers.value) return;
    const normalizedMember = normalizeMemberScopes(member);
    busy.value = true;
    notice.value = "";
    clientLogger.info("console.organization.member.update_requested");
    try {
      const updated = await consoleApi<OrganizationMembership>(
        `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/members/${encodeURIComponent(normalizedMember.user_id)}`,
        {
          method: "PUT",
          body: JSON.stringify({
            role: normalizedMember.role,
            resource_scopes: normalizedMember.resource_scopes.map((scope) => ({
              resource: scope.resource,
              action: scope.action,
            })),
          }),
        },
      );
      organizationMembers.value = organizationMembers.value.map((current) =>
        current.user_id === updated.user_id ? updated : current,
      );
      notice.value = t("console.notice.member_updated");
      clientLogger.info("console.organization.member.update_completed");
    } catch (error) {
      notice.value = messageFor(error);
      clientLogger.warn("console.organization.member.update_failed", {
        error_type: error instanceof Error ? error.name : "unknown",
      });
    } finally {
      busy.value = false;
    }
  }

  async function removeOrganizationMember(member: OrganizationMembership): Promise<void> {
    if (!activeOrganizationId.value || !canManageMembers.value) return;
    busy.value = true;
    notice.value = "";
    clientLogger.info("console.organization.member.remove_requested");
    try {
      await consoleApi<void>(
        `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/members/${encodeURIComponent(member.user_id)}`,
        { method: "DELETE" },
      );
      organizationMembers.value = organizationMembers.value.filter(
        (current) => current.user_id !== member.user_id,
      );
      notice.value = t("console.notice.member_removed");
      clientLogger.info("console.organization.member.remove_completed");
    } catch (error) {
      notice.value = messageFor(error);
      clientLogger.warn("console.organization.member.remove_failed", {
        error_type: error instanceof Error ? error.name : "unknown",
      });
    } finally {
      busy.value = false;
    }
  }

  function normalizeNewMemberScopes(): void {
    newMemberScopes.value = supportedScopesForRole(
      newMemberRole.value,
      newMemberScopes.value,
    );
  }

  function normalizeMemberScopes(member: OrganizationMembership): OrganizationMembership {
    return {
      ...member,
      resource_scopes: supportedScopesForRole(member.role, member.resource_scopes),
    };
  }

  function roleLabel(role: OrganizationRole): string {
    return t(`console.roles.${role}`);
  }

  function resetOrganizationMembers(): void {
    organizationMembers.value = [];
    organizationInvitations.value = [];
    resetInvitationForm();
  }

  function resetInvitationForm(): void {
    newMemberEmail.value = "";
    newMemberRole.value = "viewer";
    newMemberScopes.value = [{ resource: "console.control_modules", action: "read" }];
  }

  return {
    organizationMembers,
    organizationInvitations,
    newMemberEmail,
    newMemberRole,
    newMemberScopes,
    canManageOrganizationMembers: canManageMembers,
    availableMemberRoleOptions,
    availableNewMemberScopeOptions,
    loadOrganizationMembers,
    loadOrganizationInvitations,
    addOrganizationMember,
    revokeOrganizationInvitation,
    saveOrganizationMember,
    removeOrganizationMember,
    normalizeNewMemberScopes,
    roleLabel,
    resetOrganizationMembers,
  };
}
