<script setup lang="ts">
import { computed, ref } from "vue";
import { Check, ShieldCheck } from "@lucide/vue";
import { t } from "../../i18n";
import { clientLogger } from "../../utils/clientLogger";

type RoleId = "member" | "creator" | "developer" | "admin";

const selectedRole = ref<RoleId>("member");

const roles = computed(() => [
  { id: "member" as const, name: t("about.access.role.member"), modules: ["dashboard", "welcome"] },
  { id: "creator" as const, name: t("about.access.role.creator"), modules: ["dashboard", "creator-alerts", "dev-blog"] },
  { id: "developer" as const, name: t("about.access.role.developer"), modules: ["dashboard", "dev-blog", "logs", "health"] },
  { id: "admin" as const, name: t("about.access.role.admin"), modules: ["dashboard", "access", "muxivo-core", "logs", "health"] },
]);

const activeRole = computed(() => roles.value.find((role) => role.id === selectedRole.value) ?? roles.value[0]);

function selectRole(role: RoleId) {
  selectedRole.value = role;
  clientLogger.info("access_preview_role_selected", { role });
}
</script>

<template>
  <section class="access-preview" :aria-label="$t('about.access.aria')">
    <div class="access-preview-copy">
      <span class="eyebrow">{{ $t("about.access.eyebrow") }}</span>
      <h2>{{ $t("about.access.heading") }}</h2>
      <p>{{ $t("about.access.body") }}</p>
    </div>

    <div class="access-preview-workspace">
      <div class="access-preview-roles" role="tablist" :aria-label="$t('about.access.roles_aria')">
        <button
          v-for="role in roles"
          :key="role.id"
          type="button"
          role="tab"
          :aria-selected="selectedRole === role.id"
          :class="{ active: selectedRole === role.id }"
          @click="selectRole(role.id)"
        >
          {{ role.name }}
        </button>
      </div>

      <div class="access-preview-modules" role="tabpanel">
        <div class="access-preview-status"><ShieldCheck :size="17" /><span>{{ activeRole.name }}</span><small>{{ $t("about.access.workspace") }}</small></div>
        <strong>{{ $t("about.access.visible_modules") }}</strong>
        <div class="access-preview-module-list">
          <span v-for="module in activeRole.modules" :key="module"><Check :size="14" />{{ $t(`module.${module}`) }}</span>
        </div>
      </div>
    </div>
  </section>
</template>
