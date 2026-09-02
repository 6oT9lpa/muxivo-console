<script setup lang="ts">
import { Bot, BrainCircuit, Database, RadioTower, ServerCog, ShieldCheck } from "@lucide/vue";
import { computed, defineAsyncComponent } from "vue";
import RevealOnScroll from "../components/common/RevealOnScroll.vue";
import FeatureCard from "../components/landing/FeatureCard.vue";
import HeroText from "../components/landing/HeroText.vue";
import { t } from "../i18n";

const ModerationDemo = defineAsyncComponent(() => import("../components/landing/ModerationDemo.vue"));

const features = computed(() => [
  {
    index: "01", title: t("home.feature.ai.title"), text: t("home.feature.ai.text"), metric: t("home.feature.ai.metric"), metricLabel: t("home.feature.ai.metric_label"), live: true,
  },
  {
    index: "02", title: t("home.feature.creator.title"), text: t("home.feature.creator.text"), metric: t("home.feature.creator.metric"), metricLabel: t("home.feature.creator.metric_label"),
  },
  {
    index: "03", title: t("home.feature.activity.title"), text: t("home.feature.activity.text"), metric: t("home.feature.activity.metric"), metricLabel: t("home.feature.activity.metric_label"),
  },
  {
    index: "04", title: t("home.feature.voice.title"), text: t("home.feature.voice.text"), metric: t("home.feature.voice.metric"), metricLabel: t("home.feature.voice.metric_label"),
  },
  {
    index: "05", title: t("home.feature.stats.title"), text: t("home.feature.stats.text"), metric: t("home.feature.stats.metric"), metricLabel: t("home.feature.stats.metric_label"),
  },
  {
    index: "06", title: t("home.feature.logs.title"), text: t("home.feature.logs.text"), metric: t("home.feature.logs.metric"), metricLabel: t("home.feature.logs.metric_label"), live: true,
  },
]);

const aiCapabilities = computed(() => [
  {
    icon: ShieldCheck,
    title: t("home.ai.signal.title"), text: t("home.ai.signal.text"),
  },
  {
    icon: BrainCircuit,
    title: t("home.ai.model.title"), text: t("home.ai.model.text"),
  },
  {
    icon: ServerCog,
    title: t("home.ai.control.title"), text: t("home.ai.control.text"),
  },
  {
    icon: Database,
    title: t("home.ai.audit.title"), text: t("home.ai.audit.text"),
  },
]);
</script>

<template>
  <main class="public-page">
    <RevealOnScroll>
      <HeroText
        :kicker="$t('home.kicker')"
        :title="$t('home.title')"
        :body="$t('home.body')"
      />
    </RevealOnScroll>

    <section class="feature-grid" :aria-label="$t('home.why_muxivo')">
      <RevealOnScroll
        v-for="feature in features"
        :key="feature.index"
        :delay="Number(feature.index) * 45"
      >
        <FeatureCard
          :index="feature.index"
          :title="feature.title"
          :text="feature.text"
          :metric="feature.metric"
          :metric-label="feature.metricLabel"
          :live="feature.live"
        />
      </RevealOnScroll>
    </section>

    <RevealOnScroll tag="section" class="ai-story-band">
      <div class="ai-story-copy">
        <span class="eyebrow">Muxivo Core</span>
        <h2>{{ $t("home.ai.heading") }}</h2>
        <p>{{ $t("home.ai.body") }}</p>
      </div>
      <div class="ai-story-grid" :aria-label="$t('home.ai.capabilities')">
        <article v-for="item in aiCapabilities" :key="item.title">
          <component :is="item.icon" :size="22" />
          <div>
            <strong>{{ item.title }}</strong>
            <p>{{ item.text }}</p>
          </div>
        </article>
      </div>
    </RevealOnScroll>

    <RevealOnScroll>
      <ModerationDemo />
    </RevealOnScroll>

    <RevealOnScroll tag="section" class="showcase-band">
      <div class="showcase-copy">
        <span class="eyebrow">{{ $t("home.stack.eyebrow") }}</span>
        <h2>{{ $t("home.stack.heading") }}</h2>
        <p>{{ $t("home.stack.body") }}</p>
      </div>
      <div class="showcase-stack" aria-hidden="true">
        <div><ShieldCheck :size="20" /> {{ $t("home.stack.permissions") }}</div>
        <div><RadioTower :size="20" /> {{ $t("home.stack.creator") }}</div>
        <div><Bot :size="20" /> {{ $t("home.stack.ai") }}</div>
      </div>
    </RevealOnScroll>
  </main>
</template>
