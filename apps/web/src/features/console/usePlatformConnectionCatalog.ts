import { computed, ref, type ComputedRef, type Ref } from "vue";

import { consoleApi, ConsoleApiError } from "../../api/consoleApi";
import type { TranslationParams } from "../../i18n";
import { clientLogger } from "../../utils/clientLogger";
import type {
  ConnectablePlatform,
  ConnectionWizardCopy,
} from "../../utils/connectionWizard";
import type {
  PlatformConnection,
  PlatformConnectionCandidate,
  PlatformConnectionCandidateCatalog,
} from "./types";

type Translate = (key: string, params?: TranslationParams) => string;
type ConnectionLifecycleAction = "reauthorize" | "revoke" | "disconnect";

type PlatformConnectionCatalogDependencies = {
  t: Translate;
  busy: Ref<boolean>;
  notice: Ref<string>;
  messageFor: (error: unknown) => string;
  activeOrganizationId: ComputedRef<string>;
  canReadPlatformConnections: ComputedRef<boolean>;
  canManagePlatformConnections: ComputedRef<boolean>;
  localizedConnectionWizardOptions: ComputedRef<ConnectionWizardCopy[]>;
  platformLabel: (platform: PlatformConnection["platform"]) => string;
  connectionStatusLabel: (status: PlatformConnection["status"]) => string;
  resetPlatformConnectionDetails: () => void;
  resetDiscordConnectionDetails: () => void;
};

/** Owns browser-safe connection discovery, selection and lifecycle actions. */
export function usePlatformConnectionCatalog(
  dependencies: PlatformConnectionCatalogDependencies,
) {
  const {
    t,
    busy,
    notice,
    messageFor,
    activeOrganizationId,
    canReadPlatformConnections,
    canManagePlatformConnections,
    localizedConnectionWizardOptions,
    platformLabel,
    connectionStatusLabel,
    resetPlatformConnectionDetails,
    resetDiscordConnectionDetails,
  } = dependencies;

  const platform = ref<ConnectablePlatform>("discord");
  const connectionCandidates = ref<PlatformConnectionCandidate[]>([]);
  const connectionCandidatesIdentityLinked = ref<boolean | null>(null);
  const connectionCandidatesLoading = ref(false);
  const connectionCandidatesUnavailable = ref(false);
  const selectedConnectionCandidateId = ref("");
  const connections = ref<PlatformConnection[]>([]);
  const selectedConnectionId = ref("");
  const selectedDiscordConnectionId = ref("");

  const usableConnections = computed(() =>
    connections.value.filter(
      (connection) => connection.status === "active" || connection.status === "degraded",
    ),
  );
  const usableDiscordConnections = computed(() =>
    usableConnections.value.filter((connection) => connection.platform === "discord"),
  );
  const selectedConnectionWizard = computed(
    () =>
      localizedConnectionWizardOptions.value.find((option) => option.platform === platform.value) ??
      localizedConnectionWizardOptions.value[0],
  );
  const selectedConnection = computed(
    () =>
      usableConnections.value.find((connection) => connection.id === selectedConnectionId.value) ??
      null,
  );
  const selectedDiscordConnection = computed(
    () =>
      usableDiscordConnections.value.find(
        (connection) => connection.id === selectedDiscordConnectionId.value,
      ) ?? null,
  );
  const canRunSelectedDiscordWrites = computed(
    () => selectedDiscordConnection.value?.status === "active",
  );
  const selectableConnectionCandidates = computed(() =>
    connectionCandidates.value.filter(
      (candidate) =>
        !connections.value.some(
          (connection) =>
            connection.platform === candidate.platform &&
            connection.external_resource_id === candidate.external_resource_id,
        ),
    ),
  );
  const selectedConnectionCandidate = computed(
    () =>
      selectableConnectionCandidates.value.find(
        (candidate) => candidate.external_resource_id === selectedConnectionCandidateId.value,
      ) ?? null,
  );

  async function loadConnections(): Promise<void> {
    if (!activeOrganizationId.value || !canReadPlatformConnections.value) {
      resetPlatformConnectionCatalog();
      clientLogger.info("console.connection.list.load_skipped", {
        has_active_organization: Boolean(activeOrganizationId.value),
      });
      return;
    }
    busy.value = true;
    notice.value = "";
    clientLogger.info("console.connection.list.load_requested");
    try {
      const payload = await consoleApi<{ items: PlatformConnection[] }>(
        `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections`,
      );
      connections.value = payload.items;
      selectedConnectionId.value = usableConnections.value[0]?.id ?? "";
      selectedDiscordConnectionId.value = usableDiscordConnections.value[0]?.id ?? "";
      syncSelectedConnectionCandidate();
      clientLogger.info("console.connection.list.loaded", {
        count: payload.items.length,
      });
    } catch (error) {
      resetPlatformConnectionCatalog();
      notice.value = messageFor(error);
      clientLogger.warn("console.connection.list.load_failed", {
        error_type: error instanceof Error ? error.name : "unknown",
      });
    } finally {
      busy.value = false;
    }
  }

  async function loadConnectionCandidates(): Promise<void> {
    if (!activeOrganizationId.value || !canManagePlatformConnections.value) {
      resetConnectionCandidateCatalog();
      clientLogger.info("console.connection.candidates.load_skipped", {
        has_active_organization: Boolean(activeOrganizationId.value),
      });
      return;
    }
    const requestedPlatform = platform.value;
    const requestedOrganizationId = activeOrganizationId.value;
    connectionCandidatesLoading.value = true;
    connectionCandidatesUnavailable.value = false;
    clientLogger.info("console.connection.candidates.load_requested", {
      platform: requestedPlatform,
    });
    try {
      const payload = await consoleApi<PlatformConnectionCandidateCatalog>(
        `/api/v1/organizations/${encodeURIComponent(requestedOrganizationId)}/platform-connection-candidates?platform=${encodeURIComponent(requestedPlatform)}`,
      );
      if (
        requestedPlatform !== platform.value ||
        requestedOrganizationId !== activeOrganizationId.value
      ) {
        return;
      }
      connectionCandidates.value = payload.items;
      connectionCandidatesIdentityLinked.value = payload.identity_linked;
      syncSelectedConnectionCandidate();
      clientLogger.info("console.connection.candidates.loaded", {
        count: payload.items.length,
        identity_linked: payload.identity_linked,
      });
    } catch (error) {
      if (
        requestedPlatform !== platform.value ||
        requestedOrganizationId !== activeOrganizationId.value
      ) {
        return;
      }
      resetConnectionCandidateCatalog();
      connectionCandidatesUnavailable.value = error instanceof ConsoleApiError && error.status === 503;
      if (!connectionCandidatesUnavailable.value) {
        notice.value = messageFor(error);
      }
      clientLogger.warn("console.connection.candidates.load_failed", {
        error_type: error instanceof Error ? error.name : "unknown",
        unavailable: connectionCandidatesUnavailable.value,
      });
    } finally {
      if (
        requestedPlatform === platform.value &&
        requestedOrganizationId === activeOrganizationId.value
      ) {
        connectionCandidatesLoading.value = false;
      }
    }
  }

  function selectConnectionWizard(nextPlatform: ConnectablePlatform): void {
    platform.value = nextPlatform;
    resetConnectionCandidateCatalog();
    clientLogger.info("console.connection.wizard.platform_selected", {
      platform: nextPlatform,
    });
    void loadConnectionCandidates();
  }

  async function connectPlatform(): Promise<void> {
    if (!activeOrganizationId.value || !selectedConnectionCandidate.value) {
      notice.value = t("console.connections.select_candidate_required");
      return;
    }
    busy.value = true;
    notice.value = "";
    clientLogger.info("console.connection.connect.requested", {
      platform: platform.value,
    });
    try {
      const connection = await consoleApi<PlatformConnection>(
        `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections`,
        {
          method: "POST",
          body: JSON.stringify({
            platform: platform.value,
            external_resource_id: selectedConnectionCandidate.value.external_resource_id,
          }),
        },
      );
      selectedConnectionCandidateId.value = "";
      connections.value = [connection, ...connections.value];
      syncSelectedConnectionCandidate();
      notice.value = t("console.notice.connection_pending", {
        platform: platformLabel(connection.platform),
      });
      clientLogger.info("console.connection.connect.completed", {
        platform: connection.platform,
        status: connection.status,
      });
    } catch (error) {
      notice.value = messageFor(error);
      clientLogger.warn("console.connection.connect.failed", {
        error_type: error instanceof Error ? error.name : "unknown",
      });
    } finally {
      busy.value = false;
    }
  }

  async function runConnectionLifecycle(
    connection: PlatformConnection,
    action: ConnectionLifecycleAction,
  ): Promise<void> {
    if (!activeOrganizationId.value) return;
    const suffix =
      action === "reauthorize"
        ? "reauthorizations"
        : action === "revoke"
          ? "revocations"
          : "";
    const path =
      action === "disconnect"
        ? `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections/${encodeURIComponent(connection.id)}`
        : `/api/v1/organizations/${encodeURIComponent(activeOrganizationId.value)}/platform-connections/${encodeURIComponent(connection.id)}/${suffix}`;
    busy.value = true;
    notice.value = "";
    clientLogger.info("console.connection.lifecycle.requested", {
      action,
      platform: connection.platform,
    });
    try {
      const updated = await consoleApi<PlatformConnection>(path, {
        method: action === "disconnect" ? "DELETE" : "POST",
        headers: { "Idempotency-Key": `${action}:${connection.id}` },
      });
      connections.value = connections.value.map((item) =>
        item.id === updated.id ? updated : item,
      );
      resetPlatformConnectionDetails();
      resetDiscordConnectionDetails();
      notice.value = t("console.notice.connection_state", {
        platform: platformLabel(updated.platform),
        status: connectionStatusLabel(updated.status),
      });
      clientLogger.info("console.connection.lifecycle.completed", {
        action,
        platform: updated.platform,
        status: updated.status,
      });
    } catch (error) {
      notice.value = messageFor(error);
      clientLogger.warn("console.connection.lifecycle.failed", {
        action,
        error_type: error instanceof Error ? error.name : "unknown",
      });
    } finally {
      busy.value = false;
    }
  }

  function resetPlatformConnectionCatalog(): void {
    connections.value = [];
    resetConnectionCandidateCatalog();
    selectedConnectionId.value = "";
    selectedDiscordConnectionId.value = "";
  }

  function resetConnectionCandidateCatalog(): void {
    connectionCandidates.value = [];
    connectionCandidatesIdentityLinked.value = null;
    connectionCandidatesLoading.value = false;
    connectionCandidatesUnavailable.value = false;
    selectedConnectionCandidateId.value = "";
  }

  function syncSelectedConnectionCandidate(): void {
    if (
      selectedConnectionCandidateId.value &&
      selectableConnectionCandidates.value.some(
        (candidate) =>
          candidate.external_resource_id === selectedConnectionCandidateId.value,
      )
    ) {
      return;
    }
    selectedConnectionCandidateId.value =
      selectableConnectionCandidates.value[0]?.external_resource_id ?? "";
  }

  return {
    platform,
    connectionCandidates,
    connectionCandidatesIdentityLinked,
    connectionCandidatesLoading,
    connectionCandidatesUnavailable,
    selectedConnectionCandidateId,
    connections,
    selectedConnectionId,
    selectedDiscordConnectionId,
    usableConnections,
    usableDiscordConnections,
    selectedConnectionWizard,
    selectedConnection,
    selectedDiscordConnection,
    canRunSelectedDiscordWrites,
    selectableConnectionCandidates,
    selectedConnectionCandidate,
    loadConnections,
    loadConnectionCandidates,
    selectConnectionWizard,
    connectPlatform,
    runConnectionLifecycle,
    resetPlatformConnectionCatalog,
  };
}
