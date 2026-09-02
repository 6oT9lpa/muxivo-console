<script setup lang="ts">
defineProps<{
  eyebrow: string;
  title?: string;
  text?: string;
}>();
</script>

<template>
  <article class="about-panel">
    <span>{{ eyebrow }}</span>
    <h2 v-if="title">{{ title }}</h2>
    <p v-if="text">{{ text }}</p>
    <slot />
  </article>
</template>
