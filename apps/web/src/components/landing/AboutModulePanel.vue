<script setup lang="ts">
defineProps<{
  title: string;
  text: string;
  rows: string[];
  value: string;
  label: string;
}>();
</script>

<template>
  <article class="about-module-panel">
    <div>
      <span class="eyebrow">{{ label }}</span>
      <h3>{{ title }}</h3>
      <p>{{ text }}</p>
    </div>
    <div class="module-mockup" aria-hidden="true">
      <strong>{{ value }}</strong>
      <span v-for="row in rows" :key="row">{{ row }}</span>
    </div>
  </article>
</template>
