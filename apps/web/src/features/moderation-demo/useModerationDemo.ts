import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "../../i18n";
import { clientLogger } from "../../utils/clientLogger";
import { createDemoChannels, createInitialDemoMessages, createRotatingChatMessages, createRotatingLogMessages } from "./demo-content";
import { classifyDemoMessage } from "./moderationDemo.api";
import { buildModerationNotice, deriveModerationEffect } from "./moderationOutcome";
import type { DemoChannelId, DemoMessage } from "./types";

const botAvatar = "O";
const maxMessagesPerChannel = 15;

export function useModerationDemo() {
  const { locale, t } = useI18n();
  const activeChannelId = ref<DemoChannelId>("general");
  const input = ref("");
  const isClassifying = ref(false);
  const memberRestriction = ref<"timeout" | "kick" | "ban" | null>(null);
  const messages = ref<DemoMessage[]>(createInitialDemoMessages(t));
  let chatIndex = 0;
  let logIndex = 0;
  let chatTimer: number | undefined;
  let logTimer: number | undefined;

  const channels = computed(() => createDemoChannels(t));
  const activeChannel = computed(() => channels.value.find((channel) => channel.id === activeChannelId.value)!);
  const visibleMessages = computed(() => messages.value.filter((message) => message.channelId === activeChannelId.value));
  const composerDisabled = computed(() => isClassifying.value || memberRestriction.value !== null);

  function selectChannel(channelId: DemoChannelId): void {
    activeChannelId.value = channelId;
    clientLogger.info("moderation_demo_channel_selected", { channel: channelId });
  }

  async function submitMessage(): Promise<void> {
    const content = input.value.trim();
    if (!content || composerDisabled.value) {
      return;
    }

    const messageId = `visitor-${Date.now()}`;
    appendMessage({
      id: messageId,
      channelId: "general",
      author: t("home.demo.you"),
      avatar: "Y",
      content,
      timestamp: t("home.demo.now"),
      kind: "member",
      pending: true,
    });
    input.value = "";
    isClassifying.value = true;
    clientLogger.info("moderation_demo_classification_requested", { message_length: content.length });

    try {
      const decision = await classifyDemoMessage(content);
      const effect = deriveModerationEffect(decision);
      const message = messages.value.find((item) => item.id === messageId);
      const hasEnforcementAction = effect.action !== "IGNORE" && effect.action !== "LOG";
      if (message) {
        message.pending = false;
        message.flagged = hasEnforcementAction;
        // Preserve every classifier label and planned action, including safe outcomes.
        message.classification = {
          labels: decision.labels.length ? decision.labels : [decision.primary_label],
          risk: decision.risk_score,
          action: effect.action,
          executionPlan: decision.execution_plan,
        };
      }
      if (hasEnforcementAction) {
      addSystemMessage(buildModerationNotice(decision, effect));
      }
      if (effect.removesMessage && message) {
        window.setTimeout(() => {
          message.removed = true;
          clientLogger.info("moderation_demo_message_removed", { action: effect.action });
        }, 900);
      }
      if (effect.restriction) {
        memberRestriction.value = effect.restriction;
        clientLogger.warn("moderation_demo_member_restricted", { restriction: effect.restriction });
      }
      clientLogger.info("moderation_demo_classification_resolved", { action: effect.action, risk: decision.risk_score });
    } catch (error) {
      const message = messages.value.find((item) => item.id === messageId);
      if (message) {
        message.pending = false;
      }
      addSystemMessage(t("home.demo.classifier_unavailable"));
      clientLogger.error("moderation_demo_classification_failed", {
        message: error instanceof Error ? error.message : "unknown",
      });
    } finally {
      isClassifying.value = false;
    }
  }

  function addSystemMessage(content: string): void {
    appendMessage({
      id: `muxivo-discord-${Date.now()}-${messages.value.length}`,
      channelId: "general",
      author: "Muxivo Discord",
      avatar: botAvatar,
      content,
      timestamp: t("home.demo.now"),
      kind: "bot",
    });
  }

  function appendChatActivity(): void {
    const chatMessages = createRotatingChatMessages(t);
    const { author, avatar, content } = chatMessages[chatIndex % chatMessages.length];
    chatIndex += 1;
    appendMessage({ id: `chat-${Date.now()}`, channelId: "general", author, avatar, content, timestamp: t("home.demo.now"), kind: "member" });
  }

  function appendLogActivity(): void {
    const logMessages = createRotatingLogMessages(t);
    const embed = logMessages[logIndex % logMessages.length];
    logIndex += 1;
    appendMessage({ id: `log-${Date.now()}`, channelId: "server-logs", author: "Muxivo Discord", avatar: botAvatar, content: "", timestamp: t("home.demo.now"), kind: "log", embed });
  }

  function appendMessage(message: DemoMessage): void {
    const overflowIds = messages.value
      .filter((item) => item.channelId === message.channelId)
      .slice(-(maxMessagesPerChannel - 1))
      .map((item) => item.id);
    messages.value = [...messages.value.filter((item) => item.channelId !== message.channelId || overflowIds.includes(item.id)), message];
    clientLogger.info("moderation_demo_message_appended", { channel: message.channelId, kind: message.kind });
  }

  function startActivity(): void {
    chatTimer = window.setInterval(appendChatActivity, 4600);
    logTimer = window.setInterval(appendLogActivity, 6400);
    clientLogger.info("moderation_demo_activity_started");
  }

  function stopActivity(): void {
    if (chatTimer) window.clearInterval(chatTimer);
    if (logTimer) window.clearInterval(logTimer);
    clientLogger.info("moderation_demo_activity_stopped");
  }

  onMounted(startActivity);
  onBeforeUnmount(stopActivity);

  watch(locale, (nextLocale) => {
    messages.value = createInitialDemoMessages(t);
    chatIndex = 0;
    logIndex = 0;
    memberRestriction.value = null;
    input.value = "";
    clientLogger.info("moderation_demo_locale_changed", { locale: nextLocale });
  });

  return { activeChannel, activeChannelId, channels, composerDisabled, input, isClassifying, memberRestriction, selectChannel, submitMessage, visibleMessages };
}
