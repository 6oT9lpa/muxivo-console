"""HTTP metric identity value object."""

from dataclasses import dataclass


@dataclass(frozen=True, order=True, slots=True)
class HttpMetricKey:
    """Identify one method, route and response-status metric series."""

    method: str
    route: str
    status_code: int
