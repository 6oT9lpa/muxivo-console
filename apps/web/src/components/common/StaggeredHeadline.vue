<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = withDefaults(
  defineProps<{
    text: string;
    as?: string;
    speed?: number;
  }>(),
  {
    as: "h1",
    speed: 42,
  },
);

const characters = computed(() => Array.from(props.text));
const visibleText = computed(() => characters.value.slice(0, visibleCount.value).join(""));
const visibleCount = ref(0);
let timerId: number | undefined;

function clearTypingTimer() {
  if (timerId !== undefined) {
    window.clearInterval(timerId);
    timerId = undefined;
  }
}

function startTyping() {
  clearTypingTimer();
  visibleCount.value = 0;

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    visibleCount.value = characters.value.length;
    return;
  }

  timerId = window.setInterval(() => {
    visibleCount.value += 1;
    if (visibleCount.value >= characters.value.length) {
      visibleCount.value = characters.value.length;
      clearTypingTimer();
    }
  }, props.speed);
}

watch(() => props.text, startTyping);

onMounted(startTyping);
onBeforeUnmount(clearTypingTimer);
</script>

<template>
  <component :is="props.as" class="staggered-headline typewriter-headline" :aria-label="props.text">
    <span
      class="typewriter-copy"
      :class="{ 'is-complete': visibleCount >= characters.length }"
      aria-hidden="true"
    >{{ visibleText }}</span>
  </component>
</template>
