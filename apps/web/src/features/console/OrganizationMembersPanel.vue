<script setup lang="ts">
import { computed } from "vue";

import {
  canEditOrganizationMember,
  memberHasScope,
  scopesEqual,
  supportedScopesForRole,
  DEFAULT_MEMBER_SCOPE_OPTIONS,
} from "./access";
import type {
  MembershipScopeInput,
  OrganizationInvitation,
  OrganizationMembership,
  OrganizationRole,
} from "./types";
import { useI18n } from "../../i18n";
import { formatSecurityTimestamp } from "../../utils/securityPresentation";

const { t } = useI18n();

const props = defineProps<{
  actorRole: OrganizationRole | null | undefined;
  busy: boolean;
  organizationMembers: OrganizationMembership[];
  organizationInvitations: OrganizationInvitation[];
  availableMemberRoleOptions: OrganizationRole[];
  newMemberEmail: string;
  newMemberRole: OrganizationRole;
  newMemberScopes: MembershipScopeInput[];
  availableNewMemberScopeOptions: MembershipScopeInput[];
}>();

const emit = defineEmits<{
  (event: "load-members"): void;
  (event: "invite-member"): void;
  (event: "load-invitations"): void;
  (event: "revoke-invitation", invitation: OrganizationInvitation): void;
  (event: "save-member", member: OrganizationMembership): void;
  (event: "remove-member", member: OrganizationMembership): void;
  (event: "normalize-new-member-scopes"): void;
  (event: "update:newMemberEmail", value: string): void;
  (event: "update:newMemberRole", value: OrganizationRole): void;
  (event: "update:newMemberScopes", value: MembershipScopeInput[]): void;
}>();

const newMemberEmailModel = computed({
  get: () => props.newMemberEmail,
  set: (value: string) => emit("update:newMemberEmail", value),
});

const newMemberRoleModel = computed({
  get: () => props.newMemberRole,
  set: (value: OrganizationRole) => emit("update:newMemberRole", value),
});

const newMemberScopesModel = computed({
  get: () => props.newMemberScopes,
  set: (value: MembershipScopeInput[]) => emit("update:newMemberScopes", value),
});

function formatSessionTime(value: string | null): string {
  return formatSecurityTimestamp(value);
}

function roleLabel(role: OrganizationRole): string {
  return t(`console.roles.${role}`);
}

function scopeLabel(scope: MembershipScopeInput): string {
  return `${t(`console.scope.${scope.resource.replace("console.", "")}`)} · ${t(`console.scope_action.${scope.action}`)}`;
}

function memberDisplayLabel(member: OrganizationMembership): string {
  return (
    member.display_name?.trim() ||
    t("console.members.member_fallback", { value: member.user_id.slice(0, 8) })
  );
}

function invitationStatusLabel(status: OrganizationInvitation["status"]): string {
  return t(`console.invitation_status.${status}`);
}

function memberScopeOptionsForRole(role: OrganizationRole): MembershipScopeInput[] {
  return supportedScopesForRole(role, DEFAULT_MEMBER_SCOPE_OPTIONS);
}

function isNewMemberScopeSelected(scope: MembershipScopeInput): boolean {
  return props.newMemberScopes.some((item) => scopesEqual(item, scope));
}

function toggleNewMemberScope(scope: MembershipScopeInput): void {
  newMemberScopesModel.value = isNewMemberScopeSelected(scope)
    ? props.newMemberScopes.filter((item) => !scopesEqual(item, scope))
    : [...props.newMemberScopes, scope];
}

function handleMemberRoleChange(event: Event, member: OrganizationMembership): void {
  const selectedRole = (event.target as HTMLSelectElement).value;
  const nextRole =
    props.availableMemberRoleOptions.find((role) => role === selectedRole) ?? member.role;
  emit("save-member", { ...member, role: nextRole });
}

function toggleMemberScope(member: OrganizationMembership, scope: MembershipScopeInput): void {
  const resourceScopes = memberHasScope(member, scope)
    ? member.resource_scopes.filter((item) => !scopesEqual(item, scope))
    : [...member.resource_scopes, { id: null, ...scope }];
  emit("save-member", { ...member, resource_scopes: resourceScopes });
}

function canEditMember(member: OrganizationMembership): boolean {
  return canEditOrganizationMember(props.actorRole, member.role);
}
</script>

<template>
  <section
    id="console-members"
    class="platform-dashboard console-section"
    aria-labelledby="organization-members-heading"
  >
    <div class="section-heading">
      <div>
        <h3 id="organization-members-heading">{{ t("console.members.title") }}</h3>
        <p>{{ t("console.members.description") }}</p>
      </div>
      <button type="button" :disabled="busy" @click="emit('load-members')">
        {{ busy ? t("console.members.loading") : t("console.members.load") }}
      </button>
    </div>

    <form class="connection-form" @submit.prevent="emit('invite-member')">
      <label>
        {{ t("console.members.email") }}
        <input
          v-model="newMemberEmailModel"
          type="email"
          autocomplete="email"
          :placeholder="t('console.auth.email_placeholder')"
          required
        />
      </label>
      <label>
        {{ t("console.members.role") }}
        <select
          v-model="newMemberRoleModel"
          @change="emit('normalize-new-member-scopes')"
        >
          <option
            v-for="role in availableMemberRoleOptions"
            :key="role"
            :value="role"
          >
            {{ roleLabel(role) }}
          </option>
        </select>
      </label>
      <fieldset>
        <legend>{{ t("console.members.scopes") }}</legend>
        <label
          v-for="scope in availableNewMemberScopeOptions"
          :key="`${scope.resource}-${scope.action}`"
        >
          <input
            type="checkbox"
            :checked="isNewMemberScopeSelected(scope)"
            @change="toggleNewMemberScope(scope)"
          />
          {{ scopeLabel(scope) }}
        </label>
      </fieldset>
      <button :disabled="busy">
        {{ busy ? t("console.members.inviting") : t("console.members.invite") }}
      </button>
    </form>

    <div class="section-heading policy-heading">
      <div>
        <h3>{{ t("console.members.invitations_title") }}</h3>
        <p>{{ t("console.members.invitations_description") }}</p>
      </div>
      <button type="button" :disabled="busy" @click="emit('load-invitations')">
        {{ busy ? t("console.members.loading") : t("console.members.load_invitations") }}
      </button>
    </div>

    <ul v-if="organizationInvitations.length" class="health-signals invitation-list">
      <li v-for="invitation in organizationInvitations" :key="invitation.id">
        <span>
          <strong>{{ invitation.email_hint }} · {{ roleLabel(invitation.role) }}</strong>
          <small>
            {{ t("console.members.invitation_status", { value: invitationStatusLabel(invitation.status) }) }} ·
            {{ t("console.members.invitation_expires", { value: formatSessionTime(invitation.expires_at) }) }}
          </small>
          <small
            v-if="invitation.delivery_status === 'unavailable' || invitation.delivery_status === 'failed'"
          >
            {{ t("console.members.invitation_delivery_unavailable") }}
          </small>
        </span>
        <div class="invitation-actions">
          <em :data-status="invitation.status">{{ invitationStatusLabel(invitation.status) }}</em>
          <button
            v-if="invitation.status === 'pending'"
            type="button"
            :disabled="busy"
            @click="emit('revoke-invitation', invitation)"
          >
            {{ t("console.members.revoke_invitation") }}
          </button>
        </div>
      </li>
    </ul>
    <p v-else-if="!busy">{{ t("console.members.invitations_empty") }}</p>

    <ul v-if="organizationMembers.length" class="health-signals">
      <li v-for="member in organizationMembers" :key="member.user_id">
        <span>
          <strong>{{ memberDisplayLabel(member) }}</strong>
          <small v-if="member.display_name">
            {{ t("console.members.member_identifier", { value: member.user_id.slice(0, 8) }) }}
          </small>
          <small>
            {{ t("console.members.member_scopes", { role: roleLabel(member.role), count: member.resource_scopes.length }) }}
          </small>
        </span>
        <select
          v-if="canEditMember(member)"
          :value="member.role"
          :disabled="busy"
          @change="handleMemberRoleChange($event, member)"
        >
          <option
            v-for="role in availableMemberRoleOptions"
            :key="role"
            :value="role"
          >
            {{ roleLabel(role) }}
          </option>
        </select>
        <button
          v-if="canEditMember(member)"
          type="button"
          :disabled="busy"
          @click="emit('remove-member', member)"
        >
          {{ t("console.members.remove") }}
        </button>
        <div v-if="canEditMember(member)" class="connection-form">
          <label
            v-for="scope in memberScopeOptionsForRole(member.role)"
            :key="`${member.user_id}-${scope.resource}-${scope.action}`"
          >
            <input
              type="checkbox"
              :checked="memberHasScope(member, scope)"
              :disabled="busy"
              @change="toggleMemberScope(member, scope)"
            />
            {{ scopeLabel(scope) }}
          </label>
        </div>
      </li>
    </ul>
    <p v-else-if="!busy">{{ t("console.members.empty") }}</p>
  </section>
</template>
