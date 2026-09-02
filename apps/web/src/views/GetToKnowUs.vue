<script setup lang="ts">
import RevealOnScroll from "../components/common/RevealOnScroll.vue";
import { computed } from "vue";
import StaggeredHeadline from "../components/common/StaggeredHeadline.vue";
import AboutModulePanel from "../components/landing/AboutModulePanel.vue";
import AboutPanel from "../components/landing/AboutPanel.vue";
import RoleAccessPreview from "../components/landing/RoleAccessPreview.vue";
import { t } from "../i18n";

const principles = computed(() => [
  {
    title: t("about.principle.control.title"), text: t("about.principle.control.text"),
  },
  {
    title: t("about.principle.automation.title"), text: t("about.principle.automation.text"),
  },
  {
    title: t("about.principle.safety.title"), text: t("about.principle.safety.text"),
  },
  {
    title: t("about.principle.creativity.title"), text: t("about.principle.creativity.text"),
  },
]);

const pillars = computed(() =>
  ["about.pillar.ai", "about.pillar.community", "about.pillar.creator", "about.pillar.developer"].map((key) => t(key)),
);

const facts = computed(() => [
  { value: "8+", label: t("about.fact.modules") },
  { value: "4", label: t("about.fact.roles") },
  { value: "1", label: t("about.fact.activity") },
  { value: "24/7", label: t("about.fact.availability") },
]);

const modules = computed(() => ["welcome", "role-panels", "creator-alerts", "dev-blog", "muxivo-core", "logs", "server-stats", "voice-rooms", "health"].map((key) => t(`module.${key}`)));

const modulePanels = computed(() => [
  {
    title: t("about.voice.title"), text: t("about.voice.text"), rows: t("about.voice.rows").split("|"), value: t("about.voice.value"), label: t("about.voice.label"),
  },
  {
    title: t("about.stats.title"), text: t("about.stats.text"), rows: t("about.stats.rows").split("|"), value: t("about.stats.value"), label: t("about.stats.label"),
  },
  {
    title: t("about.logs.title"), text: t("about.logs.text"), rows: t("about.logs.rows").split("|"), value: t("about.logs.value"), label: t("about.logs.label"),
  },
]);
</script>

<template>
  <main class="public-page compact-public">
    <RevealOnScroll tag="section" class="about-hero">
      <div>
        <span class="eyebrow">{{ $t("about.eyebrow") }}</span>
        <StaggeredHeadline :text="$t('about.title')" />
      </div>
      <p>{{ $t("about.intro") }}</p>
    </RevealOnScroll>

    <RevealOnScroll tag="section" class="about-grid">
      <AboutPanel
        :eyebrow="$t('about.who.eyebrow')" :title="$t('about.who.title')" :text="$t('about.who.text')"
      />
      <AboutPanel
        :eyebrow="$t('about.architecture.eyebrow')" :title="$t('about.architecture.title')" :text="$t('about.architecture.text')"
      />
    </RevealOnScroll>

    <section class="principle-grid" :aria-label="$t('about.principles.label')">
      <RevealOnScroll v-for="(principle, index) in principles" :key="principle.title" :delay="index * 55">
        <AboutPanel :eyebrow="principle.title" :text="principle.text" />
      </RevealOnScroll>
    </section>

    <RevealOnScroll tag="section" class="about-transition">
      <span>{{ $t("about.transition.eyebrow") }}</span>
      <p>{{ $t("about.transition.text") }}</p>
    </RevealOnScroll>

    <RevealOnScroll tag="section" class="about-grid about-grid--support">
      <AboutPanel :eyebrow="$t('about.pillars.eyebrow')" :title="$t('about.pillars.title')">
        <ul>
          <li v-for="pillar in pillars" :key="pillar">{{ pillar }}</li>
        </ul>
      </AboutPanel>
      <AboutPanel :eyebrow="$t('about.facts')">
        <div class="facts-grid">
          <div v-for="fact in facts" :key="fact.value">
            <strong>{{ fact.value }}</strong>
            <span>{{ fact.label }}</span>
          </div>
        </div>
      </AboutPanel>
    </RevealOnScroll>

    <section class="about-module-grid" :aria-label="$t('about.previews')">
      <RevealOnScroll
        v-for="(panel, index) in modulePanels"
        :key="panel.title"
        :delay="index * 70"
      >
        <AboutModulePanel
          :title="panel.title"
          :text="panel.text"
          :rows="panel.rows"
          :value="panel.value"
          :label="panel.label"
        />
      </RevealOnScroll>
    </section>

    <RevealOnScroll>
      <RoleAccessPreview />
    </RevealOnScroll>

    <RevealOnScroll tag="section" class="about-grid about-grid--closing">
      <AboutPanel :eyebrow="$t('about.map.eyebrow')" :title="$t('about.map.title')">
        <p>{{ $t("about.map.text") }}</p>
      </AboutPanel>
    </RevealOnScroll>

    <RevealOnScroll tag="section" class="module-marquee" :aria-label="$t('about.supported_modules')">
      <span v-for="module in modules" :key="module">{{ module }}</span>
    </RevealOnScroll>
  </main>
</template>
