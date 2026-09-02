<script setup lang="ts">
import { Code2 } from "@lucide/vue";
import RevealOnScroll from "./RevealOnScroll.vue";

const currentYear = new Date().getFullYear();
const githubDocsBase =
  "https://github.com/6oT9lpa/discord-muxivo-coreation-bot/blob/main/docs";

const legalLinks = [
  { key: "footer.privacy", href: `${githubDocsBase}/PRIVACY_POLICY.md` },
  { key: "footer.terms", href: `${githubDocsBase}/TERMS_OF_SERVICE.md` },
  { key: "footer.knowledge", href: `${githubDocsBase}/KNOWLEDGE_BASE.md` },
];

const knowledgeBaseUrl = `${githubDocsBase}/KNOWLEDGE_BASE.md`;
const sourceUrl = "https://github.com/6oT9lpa/discord-muxivo-coreation-bot";

const productLinks = [
  { key: "footer.welcome", href: `${knowledgeBaseUrl}#5-welcome-alerts` },
  { key: "footer.role_panels", href: `${knowledgeBaseUrl}#4-roles-and-role-panels` },
  { key: "footer.voice_rooms", href: `${knowledgeBaseUrl}#11-dynamic-voice-rooms` },
  { key: "footer.server_stats", href: `${knowledgeBaseUrl}#10-statistics` },
];
const communityLinks = [
  { key: "footer.creator_alerts", href: `${knowledgeBaseUrl}#6-creator-alerts` },
  { key: "footer.dev_blog", href: `${knowledgeBaseUrl}#7-dev-blog` },
  { key: "footer.muxivo_core", href: `${knowledgeBaseUrl}#12-muxivo-coreation` },
  { key: "footer.logging", href: `${knowledgeBaseUrl}#9-logs-and-audit` },
];
const team = ["6oT9lpa", "Jimmy"];
</script>

<template>
  <RevealOnScroll tag="footer" class="public-footer">
    <div class="footer-grid">
      <section>
        <span>{{ $t("footer.product") }}</span>
        <a v-for="link in productLinks" :key="link.key" :href="link.href" target="_blank" rel="noreferrer">
          {{ $t(link.key) }}
        </a>
      </section>
      <section>
        <span>{{ $t("footer.legal") }}</span>
        <a v-for="link in legalLinks" :key="link.key" :href="link.href" target="_blank" rel="noreferrer">
          {{ $t(link.key) }}
        </a>
      </section>
      <section>
        <span>{{ $t("footer.community") }}</span>
        <a v-for="link in communityLinks" :key="link.key" :href="link.href" target="_blank" rel="noreferrer">
          {{ $t(link.key) }}
        </a>
      </section>
      <section>
        <span>{{ $t("footer.team") }}</span>
        <strong v-for="member in team" :key="member">{{ member }}</strong>
      </section>
    </div>

    <div class="footer-bottom">
      <p>{{ $t("footer.copyright", { year: currentYear }) }}</p>
      <div class="footer-actions">
        <a class="footer-social-link" :href="sourceUrl" target="_blank" rel="noreferrer" :aria-label="$t('footer.github')">
          <Code2 :size="17" /><span>{{ $t("footer.github") }}</span>
        </a>
        <a class="donate-button" href="https://boosty.to/6o9lpa" target="_blank" rel="noreferrer">
          {{ $t("footer.donate") }}
        </a>
      </div>
    </div>
  </RevealOnScroll>
</template>
