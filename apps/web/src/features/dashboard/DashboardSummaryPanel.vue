<script setup lang="ts">
import type { DashboardSummary, DashboardSummaryState } from "./useDashboardSummary";

defineProps<{
  state: DashboardSummaryState;
  summary: DashboardSummary | null;
}>();
</script>

<template>
  <section class="dashboard-summary" aria-labelledby="dashboard-summary-heading">
    <div class="dashboard-heading">
      <div>
        <span class="module-label">Read-only module</span>
        <h3 id="dashboard-summary-heading">Dashboard summary</h3>
      </div>
      <span v-if="summary" class="platform-label">{{ summary.platform }}</span>
    </div>
    <p v-if="state === 'idle'">Connect an active supported platform resource to load this module.</p>
    <p v-else-if="state === 'loading'" aria-live="polite">Loading resource-bound metrics…</p>
    <p v-else-if="state === 'unavailable'" role="status">This dashboard summary is unavailable. No values have been inferred or cached from another resource.</p>
    <dl v-else-if="summary" class="metric-grid">
      <div><dt>Messages today</dt><dd>{{ summary.messages_today.toLocaleString() }}</dd></div>
      <div><dt>AI flagged</dt><dd>{{ summary.ai_flagged_today.toLocaleString() }}</dd></div>
      <div><dt>Creator sources</dt><dd>{{ summary.creator_sources.toLocaleString() }}</dd></div>
      <div><dt>Bot latency</dt><dd>{{ summary.bot_latency_ms === null ? "—" : `${summary.bot_latency_ms} ms` }}</dd></div>
    </dl>
  </section>
</template>

<style scoped>
.dashboard-summary { border-top: 1px solid #2b3b58; margin-top: 22px; padding-top: 22px; }
.dashboard-heading { align-items: start; display: flex; gap: 16px; justify-content: space-between; }
.dashboard-heading h3 { margin: 4px 0 0; }
.module-label { color: #a9b7cf; font-size: .72rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.platform-label { border: 1px solid #465a7d; border-radius: 999px; color: #67e8f9; font-size: .72rem; font-weight: 800; padding: 6px 9px; text-transform: uppercase; }
.metric-grid { display: grid; gap: 10px; grid-template-columns: repeat(2, minmax(0, 1fr)); margin: 18px 0 0; }
.metric-grid div { background: #0e1727; border: 1px solid #2b3b58; border-radius: 10px; padding: 14px; }
.metric-grid dt { color: #a9b7cf; font-size: .78rem; }
.metric-grid dd { font-size: 1.35rem; font-weight: 800; margin: 5px 0 0; }
@media (max-width: 520px) { .metric-grid { grid-template-columns: 1fr; } }
</style>
