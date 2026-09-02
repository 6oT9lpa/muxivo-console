<script setup lang="ts">
defineProps<{
  index: string;
  title: string;
  text: string;
  metric?: string;
  metricLabel?: string;
  live?: boolean;
}>();
</script>

<template>
  <article class="feature-card">
    <span>{{ index }}</span>
    <h3>{{ title }}</h3>
    <p>{{ text }}</p>
    <footer v-if="metric">
      <strong :class="{ live }"><i v-if="live" />{{ metric }}</strong>
      <small>{{ metricLabel }}</small>
    </footer>
  </article>
</template>
