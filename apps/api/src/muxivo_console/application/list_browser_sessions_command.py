"""Command for listing active browser sessions."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ListBrowserSessionsCommand:
    """Identify the actor and current session for security presentation."""

    actor_id: UUID
    current_session_id: UUID
    correlation_id: UUID
