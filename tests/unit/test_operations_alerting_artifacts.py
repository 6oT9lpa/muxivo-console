from pathlib import Path


def test_prometheus_alert_rules_reference_current_console_metrics() -> None:
    metrics_source = Path("apps/api/src/muxivo_console/infrastructure/metrics.py").read_text()
    alert_rules = Path("docs/operations/prometheus-alerts.yml").read_text()

    assert "muxivo_console_http_requests_total" in metrics_source
    assert "muxivo_console_http_request_duration_seconds_sum" in metrics_source
    assert "muxivo_console_http_request_duration_seconds_count" in metrics_source
    assert "muxivo_console_http_request_duration_seconds_bucket" in metrics_source

    for metric_name in (
        "muxivo_console_http_requests_total",
        "muxivo_console_http_request_duration_seconds_bucket",
    ):
        assert metric_name in alert_rules


def test_prometheus_alert_rules_cover_foundation_operational_risks() -> None:
    alert_rules = Path("docs/operations/prometheus-alerts.yml").read_text()

    for alert_name in (
        "MuxivoConsoleHigh5xxRate",
        "MuxivoConsoleHighAuthFailureRate",
        "MuxivoConsoleHighP95Latency",
        "MuxivoConsoleConnectionLifecycleFailures",
        "MuxivoConsoleMetricsScrapeMissing",
    ):
        assert f"alert: {alert_name}" in alert_rules


def test_development_bootstrap_does_not_bypass_registration_lifecycle() -> None:
    script = Path("scripts/start-dev.ps1").read_text()

    assert "UPDATE users SET status" not in script
    assert "pending_verification" not in script


def test_deployment_proxies_readiness_without_exposing_metrics() -> None:
    bootstrap = Path("deploy/nginx-console-bootstrap.conf.example").read_text()
    final = Path("deploy/nginx-console.conf.example").read_text()

    assert "location = /readyz" in bootstrap
    assert "location = /readyz" in final
    assert "proxy_pass http://127.0.0.1:18081/readyz" in final
    assert "location = /metrics" in final
    assert "allow 127.0.0.1" in final
    assert "deny all" in final
