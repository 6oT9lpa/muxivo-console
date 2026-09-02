<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "../../i18n";
import type { OrganizationListItem, OrganizationRole } from "./types";

const props = withDefaults(
  defineProps<{
    id: string;
    modelValue: string;
    organizations: OrganizationListItem[];
    label?: string;
    disabled?: boolean;
    showActiveOrganization?: boolean;
    variant?: "sidebar" | "inline";
  }>(),
  {
    disabled: false,
    showActiveOrganization: true,
    variant: "inline",
  },
);

const emit = defineEmits<{
  "update:modelValue": [organizationId: string];
  change: [organizationId: string];
}>();

const { t } = useI18n();
const fieldLabel = computed(() => props.label ?? t("console.organization.label"));
const activeOrganization = computed(
  () =>
    props.organizations.find(
      (item) => item.organization.id === props.modelValue,
    ) ?? null,
);

function roleLabel(role: OrganizationRole): string {
  return t(`console.roles.${role}`);
}

// Keep the native select event in one place so both Console locations behave identically.
function selectOrganization(event: Event): void {
  const organizationId = (event.target as HTMLSelectElement).value;
  emit("update:modelValue", organizationId);
  emit("change", organizationId);
}
</script>

<template>
  <div
    class="organization-switcher"
    :class="[
      `organization-switcher--${variant}`,
      { 'console-organization-picker': variant === 'sidebar' },
    ]"
  >
    <label :for="id">{{ fieldLabel }}</label>
    <select
      :id="id"
      :value="modelValue"
      :disabled="disabled || !organizations.length"
      @change="selectOrganization"
    >
      <option v-if="!organizations.length" value="" disabled>
        {{ t("console.organization.empty_select") }}
      </option>
      <option
        v-for="item in organizations"
        :key="item.organization.id"
        :value="item.organization.id"
      >
        {{ item.organization.name }} · {{ roleLabel(item.membership.role) }}
      </option>
    </select>
    <p v-if="showActiveOrganization && activeOrganization" class="console-active-organization">
      <span class="console-status-dot" aria-hidden="true"></span>
      {{ t("console.organization.active") }}: {{ activeOrganization.organization.slug }}
    </p>
    <p v-else-if="showActiveOrganization" class="console-empty-organization">
      {{ t("console.organization.empty_help") }}
    </p>
  </div>
</template>
