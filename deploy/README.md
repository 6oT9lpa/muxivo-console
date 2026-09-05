# Muxivo Console deployment artifacts

These files describe an isolated deployment of Muxivo Console beside the
existing Discord Activity. Console owns the canonical `muxivo.pro` origin,
while Activity is mounted at `/activity/` through its existing local port and
FRP proxy. Console uses its own local API port `8010` and FRP port `18081`.

For the current temporary staging rollout, use `beget.ame-life.com` instead of
the canonical host. Its DNS record and dedicated certificate already exist on
the VPS; `nginx-console-beget.conf.example` contains the isolated HTTPS host.
The application environment must use the staging URL for its public base URL,
CORS allowlist, recovery links and OAuth redirect URIs while this host is active.

Do not copy credentials from the examples into Git. The production environment
must be rendered by the selected secret manager and loaded through the systemd
credential path used by `muxivo-console-api.service`.

- `muxivo-console-api.service` runs the production ASGI application and applies
  migrations before startup.
- `vault-server.hcl.example` and `vault-server.service` describe the isolated
  loopback-only staging Vault server. They use integrated raft storage and a
  TLS 1.3 listener; a public production deployment requires a reviewed HA or
  managed Vault topology.
- `vault-agent.hcl.example`, `console.env.ctmpl.example`,
  `console.env.production.ctmpl.example`, `vault-policy.hcl.example`,
  `vault-policy.production.hcl.example` and
  `muxivo-console-vault-agent.service` describe the selected HashiCorp Vault +
  Vault Agent credential path. The staging template/policy read only
  `secret/data/muxivo-console/staging`; the production template/policy read
  only `secret/data/muxivo-console/production`. Install exactly one matching
  template at `/etc/muxivo-console/console.env.ctmpl` for the target
  environment. Never use the staging template or policy for production. The
  API unit requires the agent and consumes only its root-owned runtime
  credential; it does not read a repository `.env` file.
- `muxivo-discord-vault-agent.service`, `discord-vault-agent.hcl.example`,
  `discord-control.env.ctmpl.example`, `vault-policy.discord.hcl.example` and
  `muxivo-discord-activity-vault.conf.example` describe the separate AppRole
  used by the already deployed Discord Activity. Only the HMAC signing key is
  rendered into its root-owned runtime EnvironmentFile; Discord OAuth, bot and
  platform credentials remain outside Console and are never exposed to the
  browser.
- `frpc-console.toml.example` is only a proxy fragment. Merge the `[[proxies]]`
  block into the existing `/etc/frp/frpc.toml` while preserving its server and
  authentication settings.
- `nginx-console-bootstrap.conf.example` serves the HTTP/ACME bootstrap host.
- `nginx-console.conf.example` is the final combined `muxivo.pro` HTTPS virtual
  host. It routes Console at `/`, Activity at `/activity/`, Activity API paths
  to `18080`, and Console `/api/v1` paths to `18081`.
- `nginx-console-beget.conf.example` is the temporary HTTPS staging host for
  `beget.ame-life.com`; it must not replace the existing Activity host.
- `console.env.beget.example` contains the staging URL and callback paths for
  `beget.ame-life.com`, with placeholders for all secret-manager values.
- `console.env.example` documents the required production variable names without
  containing usable secrets.
- `prometheus-console.yml.example` is a complete same-host Prometheus config
  for the loopback-only `/metrics` endpoint. Install it together with
  `docs/operations/prometheus-alerts.yml` at the referenced rules path and
  keep both files inside the monitoring network.
- `deploy/prometheus-console.dev.yml.example` and
  `docker-compose.observability.dev.yml` provide a local-only Prometheus
  smoke composition. It exposes Prometheus only on `127.0.0.1:9090` and must
  not be used as the production host configuration.
- `scripts/production_network_preflight.py` performs the final read-only public
  check for approved DNS resolution, certificate hostname validation, frontend
  reachability, API liveness/readiness and required browser security headers.
  It never sends credentials or changes DNS, Nginx, FRP or service state.

The exact rollout and validation order is documented in
`docs/operations/console-deployment.md`.
