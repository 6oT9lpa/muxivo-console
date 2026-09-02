import type { TranslationParams } from "../../i18n";
import type { DemoChannelId, DemoLogEmbed, DemoMessage } from "./types";

export type DemoTranslator = (key: string, params?: TranslationParams) => string;

export interface DemoChannel {
  id: DemoChannelId;
  label: string;
  description: string;
}

interface ChatSeed {
  author: string;
  avatar: string;
  timestamp: string;
  translationKey: string;
}

interface LogSeed {
  accent: DemoLogEmbed["accent"];
  translationKey: string;
  fields: ReadonlyArray<readonly [string, string]>;
}

const initialChatSeeds: readonly ChatSeed[] = [
  { author: "niko", avatar: "N", timestamp: "20:41", translationKey: "home.demo.chat.1" },
  { author: "luna", avatar: "L", timestamp: "20:41", translationKey: "home.demo.chat.2" },
  { author: "milo", avatar: "M", timestamp: "20:42", translationKey: "home.demo.chat.3" },
  { author: "sora", avatar: "S", timestamp: "20:42", translationKey: "home.demo.chat.4" },
  { author: "ardent", avatar: "A", timestamp: "20:43", translationKey: "home.demo.chat.5" },
  { author: "faye", avatar: "F", timestamp: "20:43", translationKey: "home.demo.chat.6" },
  { author: "kira", avatar: "K", timestamp: "20:44", translationKey: "home.demo.chat.7" },
  { author: "theo", avatar: "T", timestamp: "20:44", translationKey: "home.demo.chat.8" },
  { author: "ivy", avatar: "I", timestamp: "20:45", translationKey: "home.demo.chat.9" },
  { author: "noah", avatar: "N", timestamp: "20:45", translationKey: "home.demo.chat.10" },
];

const initialLogSeeds: readonly LogSeed[] = [
  { accent: "cyan", translationKey: "home.demo.log.joined", fields: [["member", "@arden"], ["account_age", "2y"]] },
  { accent: "violet", translationKey: "home.demo.log.voice_created", fields: [["channel", "midnight-lobby"], ["owner", "@luna"]] },
  { accent: "amber", translationKey: "home.demo.log.permissions_updated", fields: [["channel", "private-squad"], ["change", "home.demo.value.connect_enabled"]] },
  { accent: "rose", translationKey: "home.demo.log.message_edited", fields: [["channel", "#general"], ["audit", "home.demo.value.revision_saved"]] },
];

const rotatingChatSeeds: readonly Omit<ChatSeed, "timestamp">[] = [
  { author: "ardent", avatar: "A", translationKey: "home.demo.chat.5" },
  { author: "faye", avatar: "F", translationKey: "home.demo.chat.6" },
  { author: "kira", avatar: "K", translationKey: "home.demo.chat.7" },
  { author: "theo", avatar: "T", translationKey: "home.demo.chat.8" },
  { author: "ivy", avatar: "I", translationKey: "home.demo.chat.9" },
  { author: "noah", avatar: "N", translationKey: "home.demo.chat.10" },
];

const rotatingLogSeeds: readonly LogSeed[] = [
  { accent: "rose", translationKey: "home.demo.log.message_edited", fields: [["channel", "#general"], ["audit", "home.demo.value.revision_stored"]] },
  { accent: "violet", translationKey: "home.demo.log.voice_moved", fields: [["from", "midnight-lobby"], ["to", "study-room"]] },
  { accent: "cyan", translationKey: "home.demo.log.role_synced", fields: [["role", "Community"], ["status", "home.demo.value.synchronized"]] },
  { accent: "amber", translationKey: "home.demo.log.member_left", fields: [["member", "@ember"], ["session", "home.demo.value.42m"]] },
  { accent: "violet", translationKey: "home.demo.log.permissions_refreshed", fields: [["channel", "creators"], ["change", "home.demo.value.speak_enabled"]] },
];

function createEmbed(seed: LogSeed, translate: DemoTranslator): DemoLogEmbed {
  return {
    accent: seed.accent,
    title: translate(`${seed.translationKey}.title`),
    description: translate(`${seed.translationKey}.description`),
    fields: seed.fields.map(([label, value]) => ({
      label: translate(`home.demo.field.${label}`),
      value: value.startsWith("home.demo.") ? translate(value) : value,
    })),
  };
}

export function createDemoChannels(translate: DemoTranslator): DemoChannel[] {
  return [
    { id: "general", label: "general", description: translate("home.demo.channel.general") },
    { id: "server-logs", label: "server-logs", description: translate("home.demo.channel.logs") },
    { id: "dev-blog", label: "dev-blog", description: translate("home.demo.channel.dev_blog") },
  ];
}

export function createInitialDemoMessages(translate: DemoTranslator): DemoMessage[] {
  const chatMessages = initialChatSeeds.map((seed, index) => ({
    id: `general-${index + 1}`,
    channelId: "general" as const,
    author: seed.author,
    avatar: seed.avatar,
    content: translate(seed.translationKey),
    timestamp: seed.timestamp,
    kind: "member" as const,
  }));
  const logMessages = initialLogSeeds.map((seed, index) => ({
    id: `logs-${index + 1}`,
    channelId: "server-logs" as const,
    author: "Muxivo Discord",
    avatar: "O",
    content: "",
    timestamp: ["20:39", "20:40", "20:42", "20:45"][index],
    kind: "log" as const,
    embed: createEmbed(seed, translate),
  }));
  const devMessages = Array.from({ length: 10 }, (_, index) => ({
    id: `dev-${index + 1}`,
    channelId: "dev-blog" as const,
    author: "Muxivo Discord",
    avatar: "O",
    content: translate(`home.demo.dev.${index + 1}`),
    timestamp: translate(`home.demo.date.${index + 1}`),
    kind: "dev" as const,
  }));

  return [...chatMessages, ...logMessages, ...devMessages];
}

export function createRotatingChatMessages(translate: DemoTranslator) {
  return rotatingChatSeeds.map((seed) => ({ ...seed, content: translate(seed.translationKey) }));
}

export function createRotatingLogMessages(translate: DemoTranslator): DemoLogEmbed[] {
  return rotatingLogSeeds.map((seed) => createEmbed(seed, translate));
}
