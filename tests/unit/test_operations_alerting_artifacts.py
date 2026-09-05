from pathlib import Path


def test_prometheus_alert_rules_reference_current_console_metrics() -> None:
    metrics_source = Path("apps/api/src/muxivo_console/infrastructure/metrics.py").read_text()
    prometheus_config = Path("deploy/prometheus-console.yml.example").read_text()
    development_config = Path("deploy/prometheus-console.dev.yml.example").read_text()
    alert_rules = Path("docs/operations/prometheus-alerts.yml").read_text()

    assert "muxivo_console_http_requests_total" in metrics_source
    assert "muxivo_console_http_request_duration_seconds_sum" in metrics_source
    assert "muxivo_console_http_request_duration_seconds_count" in metrics_source
    assert "muxivo_console_http_request_duration_seconds_bucket" in metrics_source
    assert "rule_files:" in prometheus_config
    assert "/etc/prometheus/rules/muxivo-console-alerts.yml" in prometheus_config
    assert "api:8000" in development_config
    assert "environment: development" in development_config

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


def test_auth_failure_alert_covers_all_configured_oauth_callbacks() -> None:
    alert_rules = Path("docs/operations/prometheus-alerts.yml").read_text()

    assert "(discord|twitch|telegram|google|yandex)/.*" in alert_rules


def test_development_bootstrap_does_not_bypass_registration_lifecycle() -> None:
    script = Path("scripts/start-dev.ps1").read_text()

    assert "UPDATE users SET status" not in script
    assert "pending_verification" not in script


def test_deployment_proxies_readiness_without_exposing_metrics() -> None:
    bootstrap = Path("deploy/nginx-console-bootstrap.conf.example").read_text()
    final = Path("deploy/nginx-console.conf.example").read_text()
    staging = Path("deploy/nginx-console-beget.conf.example").read_text()
    staging_environment = Path("deploy/console.env.beget.example").read_text()

    assert "location = /readyz" in bootstrap
    assert "location = /readyz" in final
    assert "server_name beget.ame-life.com" in staging
    assert "ssl_certificate /etc/letsencrypt/live/beget.ame-life.com/fullchain.pem" in staging
    assert "return 301 https://$host$request_uri" in staging
    assert "ssl_protocols TLSv1.2 TLSv1.3" not in staging
    assert "ssl_protocols TLSv1.2 TLSv1.3" not in final
    assert "MUXIVO_CONSOLE_PUBLIC_BASE_URL=https://beget.ame-life.com" in staging_environment
    assert "MUXIVO_CONSOLE_CORS_ALLOWED_ORIGINS=https://beget.ame-life.com" in staging_environment
    assert (
        "MUXIVO_DISCORD_OAUTH_REDIRECT_URI=https://beget.ame-life.com/"
        "api/v1/auth/discord/callback" in staging_environment
    )
    assert (
        "MUXIVO_TWITCH_OAUTH_REDIRECT_URI=https://beget.ame-life.com/"
        "api/v1/auth/twitch/callback" in staging_environment
    )
    assert "<smtp.bz-password>" in staging_environment
    assert "proxy_pass http://127.0.0.1:18081/readyz" in final
    assert "proxy_pass http://127.0.0.1:18081/readyz" in staging
    assert "location = /metrics" in final
    assert "location = /metrics" in staging
    assert "allow 127.0.0.1" in final
    assert "allow 127.0.0.1" in staging
    assert "deny all" in final
    assert "deny all" in staging


def test_development_observability_composition_is_loopback_only_and_loads_rules() -> None:
    compose = Path("docker-compose.observability.dev.yml").read_text()

    assert "prom/prometheus:v2.55.1" in compose
    assert '"127.0.0.1:9090:9090"' in compose
    assert "http://127.0.0.1:9090/-/ready" in compose
    assert "prometheus-console.dev.yml.example" in compose
    assert "prometheus-alerts.yml" in compose
    assert "condition: service_healthy" in compose
