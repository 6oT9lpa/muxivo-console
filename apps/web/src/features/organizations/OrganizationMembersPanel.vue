<script setup lang="ts">
import { assignableMemberRoles } from "./organizationRolePresentation";
import type {
  OrganizationMember,
  OrganizationMemberState,
} from "./useOrganizationMembers";
import type { OrganizationRole } from "./useOrganizations";

const props = defineProps<{
  state: OrganizationMemberState;
  members: readonly OrganizationMember[];
  actorRole: OrganizationRole;
  nextCursor: string | null;
  loadingMore: boolean;
  updatingMemberId: string | null;
  mutationFailed: boolean;
}>();

const emit = defineEmits<{
  retry: [];
  loadMore: [];
  changeRole: [membershipId: string, role: OrganizationRole];
}>();

function optionsFor(member: OrganizationMember): OrganizationRole[] {
  return assignableMemberRoles(props.actorRole, member.role);
}

function changeRole(member: OrganizationMember, event: Event): void {
  const role = (event.target as HTMLSelectElement).value as OrganizationRole;
  emit("changeRole", member.membership_id, role);
}
</script>

<template>
  <section class="card workspace member-panel" aria-labelledby="organization-members-heading">
    <div class="section-heading">
      <div>
        <h2 id="organization-members-heading">Organization members</h2>
        <p>Console roles control browser access only. Platform-native permissions remain authoritative in each adapter.</p>
      </div>
      <span class="role-badge">{{ actorRole }}</span>
    </div>

    <p v-if="state === 'loading'" class="directory-state" aria-live="polite">Loading organization members…</p>
    <div v-else-if="state === 'unavailable'" class="directory-state" role="alert">
      <p>Member access could not be verified. No role controls are assumed.</p>
      <button type="button" @click="emit('retry')">Retry members</button>
    </div>
    <p v-else-if="state === 'empty'" class="directory-state">No organization members are visible.</p>

    <ul v-else-if="state === 'ready'" class="member-list">
      <li v-for="member in members" :key="member.membership_id">
        <div class="member-identity">
          <strong>{{ member.display_name }}</strong>
          <small>{{ member.user_id }}</small>
        </div>
        <label v-if="optionsFor(member).length" class="member-role">
          <span class="sr-only">Role for {{ member.display_name }}</span>
          <select
            :value="member.role"
            :disabled="updatingMemberId !== null"
            @change="changeRole(member, $event)"
          >
            <option v-for="role in optionsFor(member)" :key="role" :value="role">{{ role }}</option>
          </select>
        </label>
        <span v-else class="member-role-static">{{ member.role }}</span>
      </li>
    </ul>

    <p v-if="mutationFailed" class="member-error" role="alert">
      The role change was not applied. Reload the roster before retrying.
    </p>
    <button
      v-if="nextCursor"
      type="button"
      :disabled="loadingMore"
      @click="emit('loadMore')"
    >
      {{ loadingMore ? "Loading…" : "Load more members" }}
    </button>
  </section>
</template>

<style scoped>
.member-list {
  display: grid;
  gap: 0.75rem;
  margin: 1rem 0;
  padding: 0;
  list-style: none;
}

.member-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.9rem 1rem;
  border: 1px solid var(--border, #d8dce5);
  border-radius: 0.8rem;
}

.member-identity {
  display: grid;
  gap: 0.2rem;
  min-width: 0;
}

.member-identity small {
  overflow: hidden;
  color: var(--muted, #667085);
  text-overflow: ellipsis;
}

.member-role select {
  min-width: 8rem;
}

.member-role-static {
  font-weight: 600;
  text-transform: capitalize;
}

.member-error {
  color: #b42318;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
