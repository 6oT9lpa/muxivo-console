"""Secret-free audit facts emitted by Console application use cases."""

from dataclasses import dataclass
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
