import { computed, ref } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { TranslationParams } from "../../i18n";
import type {
  PlatformAiModerationPolicyState,
  PlatformConnection,
} from "./types";

const { consoleApiMock } = vi.hoisted(() => ({
  consoleApiMock: vi.fn(),
}));

vi.mock("../../api/consoleApi", () => ({
  consoleApi: consoleApiMock,
}));

import { usePlatformDashboard } from "./usePlatformDashboard";

const connection: PlatformConnection = {
  id: "connection-1",
  organization_id: "org-1",
  platform: "discord",
  external_resource_id: "server-1",
  status: "active",
  status_reason: null,
  granted_scopes: [],
};

const policyState: PlatformAiModerationPolicyState = {
  organization_id: "org-1",
  connection_id: "connection-1",
  is_default_policy: true,
  policy: {
    blacklist_words: ["spam"],
    allowed_domains: ["example.com"],
    labels: {},
    blacklist_action: "LOG",
    unapproved_domain_action: "REVIEW",
    context_window_days: 7,
    repeat_offender_threshold: 3,
    repeat_offender_action: "TIMEOUT",
    escalation_enabled: true,
    escalation_score_threshold: 0.8,
    escalation_half_life_days: 14,
    excluded_user_ids: [],
    excluded_role_ids: [],
    excluded_channel_ids: [],
    exclude_bots: true,
    ocr_enabled: false,
    ocr_failure_mode: "SKIP",
    ocr_max_gif_frames: 4,
    ocr_process_empty_result: false,
    test_mode: true,
    enforcement_mode: "LIMITED",
    limited_min_confidence: 0.7,
    limited_hard_rule_labels: [],
    beta_enforcement_acknowledged: true,
    allow_automated_timeout: false,
    allow_automated_kick: false,
    allow_automated_ban: false,
  },
};

function createDashboard() {
  const activeOrganizationId = ref("org-1");
  const selectedConnectionId = ref("connection-1");
  const selectedDiscordConnectionId = ref("connection-1");
  const busy = ref(false);
  const notice = ref("");
  const dashboard = usePlatformDashboard({
    t: (key: string, params?: TranslationParams) =>
      params?.count === undefined ? key : `${key}:${params.count}`,
    busy,
    notice,
    messageFor: vi.fn().mockReturnValue("neutral error"),
    activeOrganizationId: computed(() => activeOrganizationId.value),
    selectedConnectionId,
    selectedDiscordConnectionId,
    selectedConnection: computed(() => connection),
    canRunSelectedDiscordWrites: computed(() => true),
  });
  return { dashboard, activeOrganizationId, selectedConnectionId, busy, notice };
}

describe("usePlatformDashboard", () => {
  beforeEach(() => {
    consoleApiMock.mockReset();
  });

  it("loads the selected platform summary through the active organization boundary", async () => {
    consoleApiMock.mockResolvedValue({
      organization_id: "org-1",
      connection_id: "connection-1",
      platform: "discord",
      messages_today: 42,
      ai_flagged_today: 2,
      creator_sources: 1,
      bot_latency_ms: 80,
    });
    const { dashboard, busy } = createDashboard();

    await dashboard.loadPlatformDashboard();

    expect(consoleApiMock).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/platform-connections/connection-1/dashboard",
    );
    expect(dashboard.dashboardSummary.value?.messages_today).toBe(42);
    expect(busy.value).toBe(false);
  });

  it("loads read-only platform health through the selected connection boundary", async () => {
    consoleApiMock.mockResolvedValue({
      organization_id: "org-1",
      platform: "discord",
      signals: [
        {
          key: "discord.bot-latency",
          display_name: "Bot latency",
          value: "12 ms",
          status: "operational",
          latency_ms: 12,
        },
      ],
    });
    const { dashboard } = createDashboard();

    await dashboard.loadPlatformHealth();

    expect(consoleApiMock).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/platforms/discord/health",
    );
    expect(dashboard.platformHealth.value?.signals[0]?.value).toBe("12 ms");
  });

  it("appends audit pages without losing the active cursor", async () => {
    consoleApiMock
      .mockResolvedValueOnce({ items: [{ id: "event-1" }], next_cursor: "cursor-1" })
      .mockResolvedValueOnce({ items: [{ id: "event-2" }], next_cursor: null });
    const { dashboard } = createDashboard();

    await dashboard.loadOrganizationAuditEvents();
    await dashboard.loadOrganizationAuditEvents(true);

    expect(dashboard.auditEvents.value.map((event) => event.id)).toEqual([
      "event-1",
      "event-2",
    ]);
    expect(dashboard.auditEventsNextCursor.value).toBeNull();
    expect(consoleApiMock).toHaveBeenNthCalledWith(
      2,
      "/api/v1/organizations/org-1/audit-events?after=cursor-1",
    );
  });

  it("serializes policy editor values and keeps the saved state in sync", async () => {
    consoleApiMock.mockResolvedValue({
      enforcement_mode: "LIMITED",
      test_mode: true,
      is_default_policy: false,
      covered_channel_count: 1,
      log_channel_configured: true,
      label_count: 1,
      blacklist_word_count: 2,
      allowed_domain_count: 1,
      automated_timeout_enabled: false,
      automated_kick_enabled: false,
      automated_ban_enabled: false,
    });
    const { dashboard, notice } = createDashboard();
    dashboard.aiModerationPolicy.value = policyState;
    dashboard.aiModerationBlacklistWords.value = "spam\n  abuse, spam";
    dashboard.aiModerationAllowedDomains.value = "example.com,\ntrusted.example";

    await dashboard.saveDiscordAiModerationPolicy();

    expect(consoleApiMock).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/platform-connections/connection-1/ai-moderation-policy",
      {
        method: "PUT",
        body: JSON.stringify({
          ...policyState.policy,
          blacklist_words: ["spam", "abuse"],
          allowed_domains: ["example.com", "trusted.example"],
        }),
      },
    );
    expect(dashboard.aiModerationPolicy.value?.is_default_policy).toBe(false);
    expect(notice.value).toBe("console.notice.policy_saved");
  });

  it("fails closed and clears a failed resource request", async () => {
    consoleApiMock.mockRejectedValue(new Error("private upstream detail"));
    const { dashboard, notice } = createDashboard();
    dashboard.dashboardSummary.value = {
      organization_id: "org-1",
      connection_id: "connection-1",
      platform: "discord",
      messages_today: 1,
      ai_flagged_today: 0,
      creator_sources: 0,
      bot_latency_ms: null,
    };

    await dashboard.loadPlatformDashboard();

    expect(dashboard.dashboardSummary.value).toBeNull();
    expect(notice.value).toBe("neutral error");
  });

  it("clears every dashboard surface when the organization changes", () => {
    const { dashboard } = createDashboard();
    dashboard.controlModules.value = [{
      key: "module",
      display_name: "Module",
      platform: "discord",
      capability: "view",
      status: "available",
    }];
    dashboard.selectedPurpose.value = "member_log";
    dashboard.selectedPurposeChannelId.value = "channel-1";

    dashboard.resetPlatformDashboard();

    expect(dashboard.controlModules.value).toEqual([]);
    expect(dashboard.selectedPurpose.value).toBe("welcome");
    expect(dashboard.selectedPurposeChannelId.value).toBe("");
  });
});
