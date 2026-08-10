"""Secret-free audit facts emitted and queried by Console application use cases."""

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
class AuditEntry:
    """Read-only, secret-free projection exposed by the tenant audit timeline."""

    id: UUID
    correlation_id: UUID
    actor_id: UUID | None
    organization_id: UUID
    action: str
    resource_type: str
    resource_id: str | None
    result: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.action or not self.resource_type or not self.result:
            raise ValueError("Audit entry action, resource type and result are required.")
        if self.result not in {"allowed", "denied", "succeeded", "failed"}:
            raise ValueError("Audit entry result is not supported.")
        if self.created_at.tzinfo is None:
            raise ValueError("Audit entry timestamp must be timezone-aware.")
