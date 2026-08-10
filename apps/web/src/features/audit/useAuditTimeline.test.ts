import { describe, expect, it } from "vitest";
import { ConsoleApiError } from "../../api/consoleApi";
import {
  type AuditEntry,
  type AuditFilters,
  type AuditPage,
  type AuditTimelineGateway,
  useAuditTimeline,
} from "./useAuditTimeline";

const organizationId = "0198a6a2-7da7-7000-8000-000000000021";

function entry(id: string, tenant = organizationId): AuditEntry {
  return {
    id,
    correlation_id: "0198a6a2-7da7-7000-8000-000000000031",
    actor_id: "0198a6a2-7da7-7000-8000-000000000032",
    organization_id: tenant,
    action: "organization.member.role_changed",
    resource_type: "organization_membership",
    resource_id: "0198a6a2-7da7-7000-8000-000000000033",
    result: "succeeded",
    created_at: "2026-08-10T18:00:00Z",
  };
}

class StubGateway implements AuditTimelineGateway {
  calls: Array<{
    organizationId: string;
    cursor: string | undefined;
    filters: AuditFilters;
    limit?: number;
  }> = [];

  constructor(private readonly pages: Array<AuditPage | Error>) {}

  async list(
    tenantId: string,
    cursor: string | undefined,
    filters: AuditFilters,
    limit?: number,
  ): Promise<AuditPage> {
    this.calls.push({ organizationId: tenantId, cursor, filters, limit });
    const result = this.pages.shift();
    if (!result) throw new Error("No stub page");
    if (result instanceof Error) throw result;
    return result;
  }
}

class DeferredGateway implements AuditTimelineGateway {
  resolve: ((page: AuditPage) => void) | null = null;

  async list(): Promise<AuditPage> {
    return new Promise((resolve) => {
      this.resolve = resolve;
    });
  }
}

describe("useAuditTimeline", () => {
  it("loads only tenant-bound events and forwards normalized filters", async () => {
    const auditEntry = entry("0198a6a2-7da7-7000-8000-000000000041");
    const gateway = new StubGateway([{ items: [auditEntry], next_cursor: null }]);
    const timeline = useAuditTimeline(gateway);

    const state = await timeline.load(organizationId, {
      action: " organization.member.role_changed ",
      result: "succeeded",
    });

    expect(state).toBe("ready");
    expect(timeline.items.value).toEqual([auditEntry]);
    expect(gateway.calls[0]).toEqual({
      organizationId,
      cursor: undefined,
      filters: { action: "organization.member.role_changed", result: "succeeded" },
      limit: 50,
    });
  });

  it("fails closed when a response contains another tenant", async () => {
    const timeline = useAuditTimeline(
      new StubGateway([
        {
          items: [entry("0198a6a2-7da7-7000-8000-000000000042", "other-tenant")],
          next_cursor: null,
        },
      ]),
    );

    const state = await timeline.load(organizationId);

    expect(state).toBe("unavailable");
    expect(timeline.items.value).toEqual([]);
  });

  it("distinguishes an explicit server denial without exposing cached events", async () => {
    const timeline = useAuditTimeline(
      new StubGateway([new ConsoleApiError(403, "Audit access denied")]),
    );

    const state = await timeline.load(organizationId);

    expect(state).toBe("denied");
    expect(timeline.items.value).toEqual([]);
  });

  it("does not restore audit data after logout while a request is in flight", async () => {
    const gateway = new DeferredGateway();
    const timeline = useAuditTimeline(gateway);
    const pending = timeline.load(organizationId);

    timeline.clear();
    gateway.resolve?.({
      items: [entry("0198a6a2-7da7-7000-8000-000000000043")],
      next_cursor: null,
    });
    await pending;

    expect(timeline.state.value).toBe("idle");
    expect(timeline.items.value).toEqual([]);
  });

  it("hides previously verified events if pagination can no longer be confirmed", async () => {
    const first = entry("0198a6a2-7da7-7000-8000-000000000044");
    const gateway = new StubGateway([
      { items: [first], next_cursor: first.id },
      new ConsoleApiError(403, "Access revoked"),
    ]);
    const timeline = useAuditTimeline(gateway);
    await timeline.load(organizationId);

    await timeline.loadMore();

    expect(timeline.state.value).toBe("denied");
    expect(timeline.items.value).toEqual([]);
    expect(timeline.nextCursor.value).toBeNull();
  });
});
