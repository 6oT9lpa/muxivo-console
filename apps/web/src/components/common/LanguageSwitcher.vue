<script setup lang="ts">
import { Check, Languages } from "@lucide/vue";
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { type Locale, useI18n } from "../../i18n";

const { locale, setLocale, t } = useI18n();
const menuRoot = ref<HTMLElement | null>(null);
const trigger = ref<HTMLButtonElement | null>(null);
const isOpen = ref(false);
const buttonLabel = computed(() => t("common.language.choose"));
const localeOptions = computed<Array<{ code: Locale; label: string }>>(() => [
  { code: "en", label: t("common.language.english") },
  { code: "ru", label: t("common.language.russian") },
]);

function toggleMenu(): void {
  isOpen.value = !isOpen.value;
  console.debug(`[i18n] Locale menu ${isOpen.value ? "opened" : "closed"}`);
}

async function selectLocale(selectedLocale: Locale): Promise<void> {
  if (selectedLocale !== locale.value) setLocale(selectedLocale);
  isOpen.value = false;
  await nextTick();
  trigger.value?.focus();
}

function closeMenu(): void {
  isOpen.value = false;
}

// Keep the compact menu predictable for both pointer and keyboard navigation.
function handleDocumentPointerDown(event: PointerEvent): void {
  if (!menuRoot.value?.contains(event.target as Node)) closeMenu();
}

function handleDocumentKeyDown(event: KeyboardEvent): void {
  if (event.key !== "Escape" || !isOpen.value) return;
  closeMenu();
  trigger.value?.focus();
}

onMounted(() => {
  document.addEventListener("pointerdown", handleDocumentPointerDown);
  document.addEventListener("keydown", handleDocumentKeyDown);
});

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", handleDocumentPointerDown);
  document.removeEventListener("keydown", handleDocumentKeyDown);
});
</script>

<template>
  <div ref="menuRoot" class="language-menu">
    <button
      ref="trigger"
      class="icon-button language-switcher"
      type="button"
      :title="buttonLabel"
      :aria-label="buttonLabel"
      aria-haspopup="menu"
      :aria-expanded="isOpen"
      aria-controls="activity-language-menu"
      data-testid="language-menu-trigger"
      @click="toggleMenu"
    >
      <Languages :size="18" />
    </button>

    <Transition name="language-menu-popover">
      <div
        v-if="isOpen"
        id="activity-language-menu"
        class="language-menu-popover"
        role="menu"
        :aria-label="buttonLabel"
        data-testid="language-menu"
      >
        <button
          v-for="option in localeOptions"
          :key="option.code"
          class="language-menu-option"
          :class="{ active: locale === option.code }"
          type="button"
          role="menuitemradio"
          :aria-checked="locale === option.code"
          :lang="option.code"
          @click="selectLocale(option.code)"
        >
          <span>{{ option.label }}</span>
          <Check v-if="locale === option.code" :size="16" aria-hidden="true" />
        </button>
      </div>
    </Transition>
  </div>
</template>
