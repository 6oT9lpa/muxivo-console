import { computed, ref, type Ref } from "vue";

import { consoleApi } from "../../api/consoleApi";
import { clientLogger } from "../../utils/clientLogger";
import {
  ACTIVE_ORGANIZATION_STORAGE_KEY,
  chooseActiveOrganizationId,
  persistActiveOrganizationId,
} from "../../utils/organizations";
import type { TranslationParams } from "../../i18n";
import type { Organization, OrganizationListItem } from "./types";

type Translate = (key: string, params?: TranslationParams) => string;

type OrganizationSelectionDependencies = {
  t: Translate;
  busy: Ref<boolean>;
  notice: Ref<string>;
  messageFor: (error: unknown) => string;
  refreshOrganizationWorkspace: () => Promise<void>;
  resetOrganizationWorkspace: () => void;
};

/** Owns active-organization selection and its empty/loading/create states. */
export function useOrganizationSelection(
  dependencies: OrganizationSelectionDependencies,
) {
  const {
    t,
    busy,
    notice,
    messageFor,
    refreshOrganizationWorkspace,
    resetOrganizationWorkspace,
  } = dependencies;

  const organizationName = ref("");
  const organizations = ref<OrganizationListItem[]>([]);
  const organizationsLoaded = ref(false);
  const selectedOrganizationId = ref(readStoredOrganizationId());
  const activeOrganization = computed(
    () =>
      organizations.value.find(
        (item) => item.organization.id === selectedOrganizationId.value,
      ) ?? null,
  );
  const activeOrganizationId = computed(
    () => activeOrganization.value?.organization.id ?? "",
  );

  async function loadOrganizations(
    preferredOrganizationId = selectedOrganizationId.value,
  ): Promise<void> {
    busy.value = true;
    notice.value = "";
    clientLogger.info("console.organization.list.requested");
    try {
      const payload = await consoleApi<{ items: OrganizationListItem[] }>(
        "/api/v1/organizations",
      );
      organizations.value = payload.items;
      selectedOrganizationId.value = chooseActiveOrganizationId(
        payload.items,
        preferredOrganizationId,
      );
      persistActiveOrganization();
      await refreshOrganizationWorkspace();
      clientLogger.info("console.organization.list.loaded", {
        count: payload.items.length,
        has_active_organization: Boolean(selectedOrganizationId.value),
      });
    } catch (error) {
      organizations.value = [];
      selectedOrganizationId.value = "";
      resetOrganizationWorkspace();
      notice.value = messageFor(error);
      clientLogger.warn("console.organization.list.failed", {
        error_type: error instanceof Error ? error.name : "unknown",
      });
    } finally {
      organizationsLoaded.value = true;
      busy.value = false;
    }
  }

  async function selectOrganization(): Promise<void> {
    persistActiveOrganization();
    clientLogger.info("console.organization.selected", {
      has_active_organization: Boolean(selectedOrganizationId.value),
    });
    await refreshOrganizationWorkspace();
  }

  async function createOrganization(): Promise<void> {
    busy.value = true;
    notice.value = "";
    clientLogger.info("console.organization.create.requested");
    try {
      const organization = await consoleApi<Organization>("/api/v1/organizations", {
        method: "POST",
        body: JSON.stringify({ name: organizationName.value }),
      });
      organizationName.value = "";
      await loadOrganizations(organization.id);
      notice.value = t("console.notice.organization_ready", {
        name: organization.name,
        slug: organization.slug,
      });
      clientLogger.info("console.organization.create.completed");
    } catch (error) {
      notice.value = messageFor(error);
      clientLogger.warn("console.organization.create.failed", {
        error_type: error instanceof Error ? error.name : "unknown",
      });
    } finally {
      busy.value = false;
    }
  }

  function resetOrganizationSelection(): void {
    organizationName.value = "";
    organizations.value = [];
    organizationsLoaded.value = false;
    selectedOrganizationId.value = "";
    persistActiveOrganization();
  }

  function persistActiveOrganization(): void {
    if (typeof window === "undefined") return;
    persistActiveOrganizationId(window.localStorage, selectedOrganizationId.value);
  }

  return {
    organizationName,
    organizations,
    organizationsLoaded,
    selectedOrganizationId,
    activeOrganization,
    activeOrganizationId,
    loadOrganizations,
    selectOrganization,
    createOrganization,
    resetOrganizationSelection,
    persistActiveOrganization,
  };
}

function readStoredOrganizationId(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(ACTIVE_ORGANIZATION_STORAGE_KEY) ?? "";
}
