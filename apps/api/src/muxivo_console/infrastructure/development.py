"""Compatibility facade for development-only adapters."""

from muxivo_console.infrastructure.deny_by_default_organization_authorizer import (
    DenyByDefaultOrganizationAuthorizer,
)
from muxivo_console.infrastructure.static_module_catalog import StaticModuleCatalog

__all__ = ["DenyByDefaultOrganizationAuthorizer", "StaticModuleCatalog"]
