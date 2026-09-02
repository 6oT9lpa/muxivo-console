from muxivo_console.infrastructure.metrics import InMemoryHttpMetricsRecorder


def test_http_metrics_recorder_aggregates_counts_and_duration() -> None:
    recorder = InMemoryHttpMetricsRecorder()

    recorder.record_http_request(
        method="get",
        route="/healthz",
        status_code=200,
        duration_seconds=0.25,
    )
    recorder.record_http_request(
        method="GET",
        route="/healthz",
        status_code=200,
        duration_seconds=0.75,
    )

    snapshot = recorder.snapshot()
    sample = next(iter(snapshot.values()))

    assert sample.count == 2
    assert sample.duration_seconds_sum == 1.0


def test_http_metrics_recorder_renders_prometheus_text_with_escaped_labels() -> None:
    recorder = InMemoryHttpMetricsRecorder()

    recorder.record_http_request(
        method="GET",
        route='/api/"quoted"',
        status_code=500,
        duration_seconds=0.1,
    )
    recorder.record_http_request(
        method="POST",
        route="/api/v1/auth/session",
        status_code=403,
        duration_seconds=0.2,
    )

    rendered = recorder.render_prometheus()

    assert "muxivo_console_http_requests_total" in rendered
    assert "muxivo_console_http_request_duration_seconds_bucket" in rendered
    assert 'route="/api/\\"quoted\\""' in rendered
    assert 'status_code="500"' in rendered
    assert 'le="+Inf"' in rendered
