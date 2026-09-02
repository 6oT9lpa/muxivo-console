"""HTTP metric aggregate value object."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HttpMetricSample:
    """Store count and accumulated duration for one metric series."""

    count: int
    duration_seconds_sum: float
