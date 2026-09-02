import type { ModerationDemoDecision } from "./types";

const riskyTerms = [
  "spam",
  "scam",
  "nitro",
  "free",
  "airdrop",
  "token",
  "invite",
  "http://",
  "https://",
  "discord.gg",
];

export async function classifyDemoMessage(message: string): Promise<ModerationDemoDecision> {
  const normalized = message.toLowerCase();
  const hits = riskyTerms.filter((term) => normalized.includes(term));
  const hasThreat = /\b(kill|hate|ban everyone|raid)\b/i.test(message);
  const hasLink = /https?:\/\/|discord\.gg|\.com\b/i.test(message);
  const risk = Math.min(97, 18 + hits.length * 15 + (hasThreat ? 35 : 0) + (hasLink ? 18 : 0));
  const action = risk >= 78 ? "DELETE_WARN" : risk >= 55 ? "REVIEW" : risk >= 35 ? "LOG" : "IGNORE";
  const labels = [
    ...(hasLink ? ["link"] : []),
    ...(hits.length ? ["spam"] : []),
    ...(hasThreat ? ["abuse"] : []),
  ];

  await new Promise((resolve) => window.setTimeout(resolve, 420));

  return {
    risk_score: risk,
    action,
    primary_label: labels[0] ?? "safe",
    labels,
    execution_plan: action === "DELETE_WARN" ? ["DELETE", "WARN"] : action === "REVIEW" ? ["REVIEW"] : [],
  };
}
