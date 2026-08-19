"""Secret-free audit facts emitted by Console application use cases."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: UUID
    correlation_id: UUID
    actor_id: UUID | None
    organization_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    result: str

    def __post_init__(self) -> None:
        if not self.action or not self.resource_type or not self.result:
            raise ValueError("Audit event action, resource type and result are required.")


@dataclass(frozen=True, slots=True)
class AuditLogEntry:
    """A secret-free, organization-scoped audit projection for browser display."""

    id: UUID
    correlation_id: UUID
    actor_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    result: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.action or not self.resource_type or not self.result:
            raise ValueError("Audit log entry action, resource type and result are required.")
        if self.created_at.tzinfo is None:
            raise ValueError("Audit log entry creation time must be timezone-aware.")
