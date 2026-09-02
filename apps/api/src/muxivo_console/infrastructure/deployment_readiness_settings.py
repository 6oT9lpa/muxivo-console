"""Deployment readiness configuration value object."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeploymentReadinessSettings:
    """Validated public origin and production secret-manager identifier."""

    public_base_url: str
    secret_source: str
