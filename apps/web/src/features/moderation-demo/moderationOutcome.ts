import { t } from "../../i18n";
import type { ModerationDemoDecision, ModerationDemoEffect } from "./types";

const removalActions = new Set(["DELETE", "DELETE_WARN", "TIMEOUT", "KICK", "BAN"]);

export function deriveModerationEffect(decision: ModerationDemoDecision): ModerationDemoEffect {
  const action = decision.action.toUpperCase();
  const plan = new Set(decision.execution_plan.map((item) => item.toUpperCase()));
  const restriction = plan.has("BAN") || action === "BAN"
    ? "ban"
    : plan.has("KICK") || action === "KICK"
      ? "kick"
      : plan.has("TIMEOUT") || action === "TIMEOUT"
        ? "timeout"
        : null;

  return {
    action,
    removesMessage: removalActions.has(action) || [...removalActions].some((item) => plan.has(item)),
    restriction,
  };
}

export function formatRiskScore(score: number): string {
  return `${Math.round(Math.max(0, Math.min(100, score)))}%`;
}

export function buildModerationNotice(decision: ModerationDemoDecision, effect: ModerationDemoEffect): string {
  const labels = decision.labels.length ? decision.labels.join(", ") : decision.primary_label;
  const actionDescription = effect.restriction === "ban"
    ? t("home.demo.action.ban")
    : effect.restriction === "kick"
      ? t("home.demo.action.kick")
      : effect.restriction === "timeout"
        ? t("home.demo.action.timeout")
        : effect.removesMessage
          ? t("home.demo.action.removed")
          : t("home.demo.action.warning");

  return t("home.demo.notice", { labels, risk: formatRiskScore(decision.risk_score), action: actionDescription });
}
