<script setup lang="ts">
import StaggeredHeadline from "../common/StaggeredHeadline.vue";

const props = defineProps<{
  kicker: string;
  title: string;
  body: string;
}>();
</script>

<template>
  <section class="hero-section">
    <div class="hero-copy">
      <span class="eyebrow">{{ kicker }}</span>
      <StaggeredHeadline :text="props.title" />
    </div>
    <p class="hero-body">{{ body }}</p>
  </section>
</template>
