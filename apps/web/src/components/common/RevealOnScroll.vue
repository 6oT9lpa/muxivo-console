<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";

const props = withDefaults(
  defineProps<{
    tag?: string;
    delay?: number;
  }>(),
  {
    tag: "div",
    delay: 0,
  },
);

const root = ref<HTMLElement | null>(null);
const isVisible = ref(false);
let observer: IntersectionObserver | null = null;

onMounted(() => {
  if (!root.value) return;

  observer = new IntersectionObserver(
    ([entry]) => {
      isVisible.value = entry.isIntersecting;
    },
    {
      root: null,
      rootMargin: "0px 0px -8% 0px",
      threshold: 0.18,
    },
  );
  observer.observe(root.value);
});

onBeforeUnmount(() => {
  observer?.disconnect();
});
</script>

<template>
  <component
    :is="props.tag"
    ref="root"
    :class="['reveal-on-scroll', { 'is-visible': isVisible }]"
    :style="{ '--reveal-delay': `${props.delay}ms` }"
  >
    <slot />
  </component>
</template>
