<script setup lang="ts">
import { Bot, Hash, LockKeyhole, Radio, Send, ShieldAlert, Sparkles } from "@lucide/vue";
import { nextTick, onMounted, ref, TransitionGroup, watch } from "vue";
import { useModerationDemo } from "../../features/moderation-demo/useModerationDemo";
import { useI18n } from "../../i18n";
import { formatRiskScore } from "../../features/moderation-demo/moderationOutcome";

const { t } = useI18n();
const {
  activeChannel,
  activeChannelId,
  channels,
  composerDisabled,
  input,
  isClassifying,
  memberRestriction,
  selectChannel,
  submitMessage,
  visibleMessages,
} = useModerationDemo();

const messageList = ref<HTMLElement | null>(null);

async function scrollToLatestMessage() {
  await nextTick();
  const element = messageList.value;
  if (!element) return;
  // Always reveal newly appended live and visitor messages; no existing row is recreated.
  if (typeof element.scrollTo === "function") {
    element.scrollTo({ top: element.scrollHeight, behavior: "smooth" });
  } else {
    element.scrollTop = element.scrollHeight;
  }
}

watch(visibleMessages, () => {
  void scrollToLatestMessage();
}, { deep: true, flush: "post" });

onMounted(() => {
  void scrollToLatestMessage();
});
</script>

<template>
  <section class="moderation-demo" aria-labelledby="moderation-demo-title">
    <div class="moderation-demo-heading">
      <div>
        <span class="eyebrow">{{ t("home.demo.kicker") }}</span>
        <h2 id="moderation-demo-title">{{ t("home.demo.heading") }}</h2>
        <p>{{ t("home.demo.body") }}</p>
      </div>
      <div class="moderation-demo-status"><Radio :size="15" /> {{ t("home.demo.status_connected") }}</div>
    </div>

    <div class="demo-server-shell">
      <aside class="demo-channel-sidebar" :aria-label="t('home.demo.server_aria')">
        <div class="demo-server-brand"><div class="demo-server-glyph"><Bot :size="20" /></div><strong>{{ t("home.demo.server_name") }}</strong></div>
        <span class="demo-channel-group">{{ t("home.demo.text_channels") }}</span>
        <button
          v-for="channel in channels"
          :key="channel.id"
          type="button"
          :class="['demo-channel-button', { active: activeChannelId === channel.id }]"
          @click="selectChannel(channel.id)"
        >
          <Hash :size="16" /> {{ channel.label }}
        </button>
        <div class="demo-live-members"><span /><div><strong>{{ t("home.demo.members_online", { count: 10 }) }}</strong><small>{{ t("home.demo.live_activity") }}</small></div></div>
      </aside>

      <div class="demo-conversation">
        <header class="demo-conversation-header"><Hash :size="20" /><div><strong>{{ activeChannel.label }}</strong><span>{{ activeChannel.description }}</span></div><Sparkles :size="18" /></header>
        <div ref="messageList" class="demo-message-list" aria-live="polite">
          <TransitionGroup name="demo-message" tag="div" class="demo-message-stack">
            <article
            v-for="message in visibleMessages"
            :key="message.id"
            :class="['demo-message', `is-${message.kind}`, { flagged: message.flagged, removed: message.removed, pending: message.pending }]"
            >
              <span class="demo-avatar">{{ message.avatar }}</span>
              <div>
                <div class="demo-message-meta"><strong>{{ message.author }}</strong><small>{{ message.timestamp }}</small><ShieldAlert v-if="message.flagged" :size="14" /></div>
                <div v-if="message.embed" :class="['demo-log-embed', `accent-${message.embed.accent}`]">
                  <strong>{{ message.embed.title }}</strong>
                  <p>{{ message.embed.description }}</p>
                  <dl><div v-for="field in message.embed.fields" :key="field.label"><dt>{{ field.label }}</dt><dd>{{ field.value }}</dd></div></dl>
                </div>
                <template v-else>
                  <p>{{ message.removed ? t("home.demo.message_removed") : message.content }}</p>
                  <small v-if="message.classification" :class="['demo-classifier-result', { safe: message.classification.action === 'IGNORE' || message.classification.action === 'LOG' }]">
                    {{ t("home.demo.classifier_result", { labels: message.classification.labels.join(", "), risk: formatRiskScore(message.classification.risk), action: message.classification.action, plan: message.classification.executionPlan.join(" → ") || message.classification.action }) }}
                  </small>
                </template>
              </div>
            </article>
          </TransitionGroup>
        </div>
        <form v-if="activeChannelId === 'general'" class="demo-composer" @submit.prevent="submitMessage">
          <LockKeyhole v-if="memberRestriction" :size="17" />
          <input v-model="input" :disabled="composerDisabled" :placeholder="memberRestriction ? t('home.demo.restriction', { restriction: t(`home.demo.restriction.${memberRestriction}`) }) : t('home.demo.placeholder')" maxlength="800" :aria-label="t('home.demo.input_aria')" />
          <button type="submit" :disabled="composerDisabled || !input.trim()" :aria-label="t('home.demo.send')"><Send :size="18" /></button>
          <span v-if="isClassifying" class="demo-classifying">{{ t("home.demo.checking") }}</span>
        </form>
      </div>
    </div>
  </section>
</template>
