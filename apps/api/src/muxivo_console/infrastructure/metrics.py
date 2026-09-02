"""Runtime metrics adapter for the Console API process."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from threading import Lock

DEFAULT_HTTP_DURATION_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


@dataclass(frozen=True, order=True, slots=True)
class HttpMetricKey:
    method: str
    route: str
    status_code: int


@dataclass(frozen=True, slots=True)
class HttpMetricSample:
    count: int
    duration_seconds_sum: float


class InMemoryHttpMetricsRecorder:
    """Small Prometheus-compatible recorder for one API process."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._request_counts: defaultdict[HttpMetricKey, int] = defaultdict(int)
        self._duration_sums: defaultdict[HttpMetricKey, float] = defaultdict(float)
        self._duration_buckets: defaultdict[tuple[HttpMetricKey, float], int] = defaultdict(int)

    def record_http_request(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        key = HttpMetricKey(method=method.upper(), route=route, status_code=status_code)
        duration = max(0.0, duration_seconds)
        with self._lock:
            self._request_counts[key] += 1
            self._duration_sums[key] += duration
            for bucket in DEFAULT_HTTP_DURATION_BUCKETS:
                if duration <= bucket:
                    self._duration_buckets[(key, bucket)] += 1

    def snapshot(self) -> dict[HttpMetricKey, HttpMetricSample]:
        with self._lock:
            return {
                key: HttpMetricSample(
                    count=count,
                    duration_seconds_sum=self._duration_sums[key],
                )
                for key, count in self._request_counts.items()
            }

    def render_prometheus(self) -> str:
        snapshot = self.snapshot()
        lines = [
            "# HELP muxivo_console_http_requests_total Total HTTP requests handled.",
            "# TYPE muxivo_console_http_requests_total counter",
        ]
        for key, sample in sorted(snapshot.items(), key=lambda item: item[0]):
            labels = _labels_for(key)
            lines.append(f"muxivo_console_http_requests_total{{{labels}}} {sample.count}")
        lines.extend(
            [
                "# HELP muxivo_console_http_request_duration_seconds_sum "
                "Total HTTP request duration in seconds.",
                "# TYPE muxivo_console_http_request_duration_seconds_sum counter",
            ]
        )
        for key, sample in sorted(snapshot.items(), key=lambda item: item[0]):
            labels = _labels_for(key)
            lines.append(
                "muxivo_console_http_request_duration_seconds_sum"
                f"{{{labels}}} {sample.duration_seconds_sum:.6f}"
            )
        lines.extend(
            [
                "# HELP muxivo_console_http_request_duration_seconds_count "
                "HTTP request duration sample count.",
                "# TYPE muxivo_console_http_request_duration_seconds_count counter",
            ]
        )
        for key, sample in sorted(snapshot.items(), key=lambda item: item[0]):
            labels = _labels_for(key)
            lines.append(
                f"muxivo_console_http_request_duration_seconds_count{{{labels}}} {sample.count}"
            )
        lines.extend(
            [
                "# HELP muxivo_console_http_request_duration_seconds_bucket "
                "HTTP request duration buckets in seconds.",
                "# TYPE muxivo_console_http_request_duration_seconds_bucket histogram",
            ]
        )
        for key, sample in sorted(snapshot.items(), key=lambda item: item[0]):
            base_labels = _labels_for(key)
            for bucket in DEFAULT_HTTP_DURATION_BUCKETS:
                labels = f'{base_labels},le="{bucket:g}"'
                count = self._duration_buckets.get((key, bucket), 0)
                lines.append(
                    f"muxivo_console_http_request_duration_seconds_bucket{{{labels}}} {count}"
                )
            labels = f'{base_labels},le="+Inf"'
            lines.append(
                f"muxivo_console_http_request_duration_seconds_bucket{{{labels}}} {sample.count}"
            )
        return "\n".join(lines) + "\n"


def _labels_for(key: HttpMetricKey) -> str:
    return (
        f'method="{_escape_label_value(key.method)}",'
        f'route="{_escape_label_value(key.route)}",'
        f'status_code="{key.status_code}"'
    )


def _escape_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
