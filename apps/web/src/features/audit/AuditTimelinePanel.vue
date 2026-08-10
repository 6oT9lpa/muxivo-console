<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";
import type { OrganizationRole } from "../organizations/useOrganizations";
import { canAttemptAuditTimeline, formatAuditTimestamp } from "./auditPresentation";
import {
  type AuditFilters,
  type AuditResult,
  useAuditTimeline,
} from "./useAuditTimeline";

const props = defineProps<{
  organizationId: string;
  actorRole: OrganizationRole;
}>();

const timeline = useAuditTimeline();
const eligible = computed(() => canAttemptAuditTimeline(props.actorRole));
const actorIdFilter = ref("");
const actionFilter = ref("");
const resourceTypeFilter = ref("");
const resultFilter = ref<AuditResult | "">("");

watch(
  [() => props.organizationId, () => props.actorRole],
  async ([organizationId, actorRole]) => {
    timeline.clear();
    resetFilterInputs();
    if (organizationId && canAttemptAuditTimeline(actorRole)) {
      await timeline.load(organizationId);
    }
  },
  { immediate: true },
);

onUnmounted(() => timeline.clear());

async function applyFilters(): Promise<void> {
  if (!eligible.value || !props.organizationId) return;
  const filters: AuditFilters = {};
  if (actorIdFilter.value.trim()) filters.actorId = actorIdFilter.value;
  if (actionFilter.value.trim()) filters.action = actionFilter.value;
  if (resourceTypeFilter.value.trim()) filters.resourceType = resourceTypeFilter.value;
  if (resultFilter.value) filters.result = resultFilter.value;
  await timeline.load(props.organizationId, filters);
}

async function clearFilters(): Promise<void> {
  resetFilterInputs();
  if (eligible.value && props.organizationId) await timeline.load(props.organizationId);
}

function resetFilterInputs(): void {
  actorIdFilter.value = "";
  actionFilter.value = "";
  resourceTypeFilter.value = "";
  resultFilter.value = "";
}
</script>

<template>
  <section
    v-if="eligible"
    class="card workspace audit-panel"
    aria-labelledby="organization-audit-heading"
  >
    <div class="section-heading">
      <div>
        <h2 id="organization-audit-heading">Audit timeline</h2>
        <p>Console security and administration events for the selected organization.</p>
      </div>
      <span class="role-badge">{{ actorRole }}</span>
    </div>

    <form class="audit-filters" @submit.prevent="applyFilters">
      <label>
        Actor ID
        <input v-model="actorIdFilter" autocomplete="off" placeholder="Optional UUID" />
      </label>
      <label>
        Action
        <input v-model="actionFilter" maxlength="128" autocomplete="off" placeholder="Exact action" />
      </label>
      <label>
        Resource type
        <input
          v-model="resourceTypeFilter"
          maxlength="128"
          autocomplete="off"
          placeholder="Exact resource type"
        />
      </label>
      <label>
        Result
        <select v-model="resultFilter">
          <option value="">Any result</option>
          <option value="succeeded">Succeeded</option>
          <option value="failed">Failed</option>
          <option value="allowed">Allowed</option>
          <option value="denied">Denied</option>
        </select>
      </label>
      <div class="audit-filter-actions">
        <button type="submit" :disabled="timeline.state.value === 'loading'">Apply filters</button>
        <button type="button" :disabled="timeline.state.value === 'loading'" @click="clearFilters">
          Clear
        </button>
      </div>
    </form>

    <p v-if="timeline.state.value === 'loading'" class="directory-state" aria-live="polite">
      Loading audit events…
    </p>
    <div v-else-if="timeline.state.value === 'denied'" class="directory-state" role="status">
      <p>Audit access is not granted for this organization.</p>
    </div>
    <div v-else-if="timeline.state.value === 'unavailable'" class="directory-state" role="alert">
      <p>Audit history could not be verified, so cached events are hidden.</p>
      <button type="button" @click="timeline.reload">Retry audit history</button>
    </div>
    <p v-else-if="timeline.state.value === 'empty'" class="directory-state">
      No audit events match the current filters.
    </p>

    <ol v-else-if="timeline.state.value === 'ready'" class="audit-list">
      <li v-for="entry in timeline.items.value" :key="entry.id">
        <div class="audit-event-heading">
          <strong>{{ entry.action }}</strong>
          <em :data-status="entry.result">{{ entry.result }}</em>
        </div>
        <dl>
          <div><dt>Time</dt><dd>{{ formatAuditTimestamp(entry.created_at) }}</dd></div>
          <div><dt>Actor</dt><dd><code>{{ entry.actor_id ?? "system" }}</code></dd></div>
          <div><dt>Resource</dt><dd>{{ entry.resource_type }}</dd></div>
          <div><dt>Resource ID</dt><dd><code>{{ entry.resource_id ?? "—" }}</code></dd></div>
          <div><dt>Correlation</dt><dd><code>{{ entry.correlation_id }}</code></dd></div>
        </dl>
      </li>
    </ol>

    <button
      v-if="timeline.nextCursor.value"
      type="button"
      :disabled="timeline.loadingMore.value"
      @click="timeline.loadMore"
    >
      {{ timeline.loadingMore.value ? "Loading…" : "Load more audit events" }}
    </button>
  </section>
</template>

<style scoped>
.audit-filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: 0.75rem;
  align-items: end;
  margin: 1rem 0;
}

.audit-filter-actions {
  display: flex;
  gap: 0.5rem;
}

.audit-list {
  display: grid;
  gap: 0.75rem;
  margin: 1rem 0;
  padding: 0;
  list-style: none;
}

.audit-list li {
  padding: 1rem;
  border: 1px solid var(--border, #d8dce5);
  border-radius: 0.8rem;
}

.audit-event-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.audit-event-heading em {
  font-style: normal;
  text-transform: capitalize;
}

.audit-list dl {
  display: grid;
  gap: 0.35rem;
  margin: 0.75rem 0 0;
}

.audit-list dl div {
  display: grid;
  grid-template-columns: 7rem minmax(0, 1fr);
  gap: 0.75rem;
}

.audit-list dt {
  color: var(--muted, #667085);
}

.audit-list dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
}
</style>
