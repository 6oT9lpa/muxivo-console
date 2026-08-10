<script setup lang="ts">
import { onUnmounted, ref, watch } from "vue";
import { useServerStats } from "./useServerStats";

const props = defineProps<{
  organizationId: string;
  connectionId: string;
}>();

const periodDays = ref(30);
const serverStats = useServerStats();

watch(
  [() => props.organizationId, () => props.connectionId],
  async ([organizationId, connectionId]) => {
    serverStats.clear();
    periodDays.value = 30;
    if (organizationId && connectionId) {
      await serverStats.load(organizationId, connectionId, periodDays.value);
    }
  },
  { immediate: true },
);

onUnmounted(() => serverStats.clear());

async function reloadForPeriod(): Promise<void> {
  await serverStats.load(props.organizationId, props.connectionId, periodDays.value);
}
</script>

<template>
  <section class="card workspace server-stats" aria-labelledby="server-stats-heading">
    <div class="section-heading">
      <div>
        <h2 id="server-stats-heading">Server stats</h2>
        <p>Read-only aggregate activity from the selected platform connection.</p>
      </div>
      <label class="period-selector">
        Period
        <select v-model.number="periodDays" :disabled="serverStats.state.value === 'loading'" @change="reloadForPeriod">
          <option :value="7">7 days</option>
          <option :value="30">30 days</option>
          <option :value="90">90 days</option>
          <option :value="365">365 days</option>
        </select>
      </label>
    </div>

    <p v-if="serverStats.state.value === 'loading'" class="directory-state" aria-live="polite">
      Loading server statistics…
    </p>
    <div v-else-if="serverStats.state.value === 'unavailable'" class="directory-state" role="alert">
      <p>Server statistics could not be verified. No cached values are shown.</p>
      <button type="button" @click="serverStats.reload">Retry</button>
    </div>

    <template v-else-if="serverStats.state.value === 'ready' && serverStats.stats.value">
      <dl class="stats-grid">
        <div><dt>Messages</dt><dd>{{ serverStats.stats.value.summary.total_messages }}</dd></div>
        <div><dt>Active users</dt><dd>{{ serverStats.stats.value.summary.active_users }}</dd></div>
        <div><dt>DAU</dt><dd>{{ serverStats.stats.value.summary.daily_active_users }}</dd></div>
        <div><dt>WAU</dt><dd>{{ serverStats.stats.value.summary.weekly_active_users }}</dd></div>
        <div><dt>MAU</dt><dd>{{ serverStats.stats.value.summary.monthly_active_users }}</dd></div>
        <div><dt>Members</dt><dd>{{ serverStats.stats.value.summary.current_member_count }}</dd></div>
        <div><dt>Net growth</dt><dd>{{ serverStats.stats.value.summary.net_member_growth }}</dd></div>
        <div><dt>Moderation events</dt><dd>{{ serverStats.stats.value.summary.moderation_events }}</dd></div>
        <div><dt>Voice minutes</dt><dd>{{ serverStats.stats.value.summary.total_voice_minutes }}</dd></div>
      </dl>

      <div class="stats-columns">
        <section aria-labelledby="top-channels-heading">
          <h3 id="top-channels-heading">Top channels</h3>
          <ol v-if="serverStats.stats.value.channels.length" class="compact-list">
            <li v-for="channel in serverStats.stats.value.channels.slice(0, 10)" :key="channel.channel_id">
              <span>#{{ channel.channel_name }}</span>
              <strong>{{ channel.messages }}</strong>
            </li>
          </ol>
          <p v-else class="empty-state">No channel activity in this period.</p>
        </section>

        <section aria-labelledby="daily-activity-heading">
          <h3 id="daily-activity-heading">Recent daily activity</h3>
          <ol v-if="serverStats.stats.value.daily.length" class="compact-list">
            <li v-for="day in serverStats.stats.value.daily.slice(-10)" :key="day.date">
              <span>{{ day.date }}</span>
              <strong>{{ day.count }}</strong>
            </li>
          </ol>
          <p v-else class="empty-state">No daily activity in this period.</p>
        </section>
      </div>
    </template>
  </section>
</template>

<style scoped>
.period-selector {
  min-width: 8rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(8rem, 1fr));
  gap: 0.75rem;
  margin: 1rem 0;
}

.stats-grid div {
  padding: 0.8rem;
  border: 1px solid var(--border, #d8dce5);
  border-radius: 0.75rem;
}

.stats-grid dt {
  color: var(--muted, #667085);
  font-size: 0.85rem;
}

.stats-grid dd {
  margin: 0.25rem 0 0;
  font-size: 1.25rem;
  font-weight: 700;
}

.stats-columns {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
  gap: 1rem;
}

.compact-list {
  display: grid;
  gap: 0.4rem;
  padding: 0;
  list-style: none;
}

.compact-list li {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.55rem 0;
  border-bottom: 1px solid var(--border, #d8dce5);
}
</style>
