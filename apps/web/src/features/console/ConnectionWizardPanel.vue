<script setup lang="ts">
import { computed } from "vue";

import { useI18n } from "../../i18n";
import type {
  ConnectablePlatform,
  ConnectionWizardCopy,
} from "../../utils/connectionWizard";
import type {
  PlatformConnectionCandidate,
} from "./types";

const { t } = useI18n();

const props = defineProps<{
  busy: boolean;
  platform: ConnectablePlatform;
  localizedConnectionWizardOptions: ConnectionWizardCopy[];
  selectedConnectionWizard: ConnectionWizardCopy;
  connectionCandidatesLoading: boolean;
  connectionCandidatesUnavailable: boolean;
  connectionCandidatesIdentityLinked: boolean | null;
  selectableConnectionCandidates: PlatformConnectionCandidate[];
  selectedConnectionCandidateId: string;
}>();

const emit = defineEmits<{
  (event: "select-platform", platform: ConnectablePlatform): void;
  (event: "connect"): void;
  (event: "load-candidates"): void;
  (event: "link-identity", platform: ConnectablePlatform): void;
  (event: "update:selectedConnectionCandidateId", value: string): void;
}>();

const selectedCandidateModel = computed({
  get: () => props.selectedConnectionCandidateId,
  set: (value: string) => emit("update:selectedConnectionCandidateId", value),
});
</script>

<template>
  <section class="platform-dashboard" aria-labelledby="connection-wizard-heading">
    <div class="section-heading">
      <div>
        <h3 id="connection-wizard-heading">{{ selectedConnectionWizard.title }}</h3>
        <p>{{ selectedConnectionWizard.summary }}</p>
      </div>
    </div>

    <div class="platform-choice-grid" role="list" :aria-label="t('console.connections.type_aria')">
      <button
        v-for="option in localizedConnectionWizardOptions"
        :key="option.platform"
        type="button"
        :class="{ active: platform === option.platform }"
        :aria-pressed="platform === option.platform"
        @click="emit('select-platform', option.platform)"
      >
        <strong>{{ option.title }}</strong>
        <span>{{ option.summary }}</span>
      </button>
    </div>

    <ol class="health-signals">
      <li v-for="step in selectedConnectionWizard.preflightSteps" :key="step">
        <span><strong>{{ step }}</strong></span>
      </li>
    </ol>

    <form class="connection-form" @submit.prevent="emit('connect')">
      <label>
        {{ selectedConnectionWizard.candidateLabel }}
        <select
          v-model="selectedCandidateModel"
          :disabled="busy || connectionCandidatesLoading || !selectableConnectionCandidates.length"
          required
        >
          <option value="" disabled>
            {{
              connectionCandidatesLoading
                ? t("console.connections.loading_candidates")
                : t("console.connections.select_candidate")
            }}
          </option>
          <option
            v-for="candidate in selectableConnectionCandidates"
            :key="candidate.external_resource_id"
            :value="candidate.external_resource_id"
          >
            {{ candidate.display_name }}
          </option>
        </select>
      </label>
      <p>{{ selectedConnectionWizard.candidateHelp }}</p>
      <p v-if="connectionCandidatesLoading" class="connection-feedback" role="status">
        {{ t("console.connections.loading_candidates") }}
      </p>
      <p v-else-if="connectionCandidatesUnavailable" class="connection-feedback" role="alert">
        {{ t("console.connections.catalog_unavailable") }}
        <button type="button" class="inline-action" :disabled="busy" @click="emit('load-candidates')">
          {{ t("console.connections.refresh_candidates") }}
        </button>
      </p>
      <p v-else-if="connectionCandidatesIdentityLinked === false" class="connection-feedback">
        {{ t("console.connections.identity_required") }}
      </p>
      <p v-else-if="!selectableConnectionCandidates.length" class="connection-feedback">
        {{ t("console.connections.no_candidates") }}
      </p>
      <p v-if="platform === 'discord'">
        {{ t("console.connections.ownership_discord") }}
        <button
          type="button"
          class="inline-action"
          :disabled="busy"
          @click="emit('link-identity', 'discord')"
        >
          {{ t("console.connections.link_identity", { platform: "Discord" }) }}
        </button>
      </p>
      <p v-else-if="platform === 'twitch'">
        {{ t("console.connections.ownership_twitch") }}
        <button
          type="button"
          class="inline-action"
          :disabled="busy"
          @click="emit('link-identity', 'twitch')"
        >
          {{ t("console.connections.link_identity", { platform: "Twitch" }) }}
        </button>
      </p>
      <button :disabled="busy || connectionCandidatesLoading || !selectedConnectionCandidateId">
        {{ busy ? t("console.members.loading") : selectedConnectionWizard.actionLabel }}
      </button>
    </form>
    <p>{{ t("console.connections.security_note") }}</p>
  </section>
</template>
