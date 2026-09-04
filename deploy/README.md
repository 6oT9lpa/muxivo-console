# Muxivo Console deployment artifacts

These files describe an isolated deployment of Muxivo Console beside the
existing Discord Activity. The existing Activity keeps its current public host,
local port and FRP proxy. Console uses its own local API port `8010`, FRP port
`18081` and host `console.muxivo.pro`.

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
- `vault-agent.hcl.example`, `console.env.ctmpl.example`,
  `vault-policy.hcl.example` and `muxivo-console-vault-agent.service` describe
  the selected HashiCorp Vault + Vault Agent credential path. The API unit
  requires the agent and consumes only its root-owned runtime credential; it
  does not read a repository `.env` file.
- `frpc-console.toml.example` is only a proxy fragment. Merge the `[[proxies]]`
  block into the existing `/etc/frp/frpc.toml` while preserving its server and
  authentication settings.
- `nginx-console-bootstrap.conf.example` serves the HTTP/ACME bootstrap host.
- `nginx-console.conf.example` is the final HTTPS virtual host.
- `nginx-console-beget.conf.example` is the temporary HTTPS staging host for
  `beget.ame-life.com`; it must not replace the existing Activity host.
- `console.env.beget.example` contains the staging URL and callback paths for
  `beget.ame-life.com`, with placeholders for all secret-manager values.
- `console.env.example` documents the required production variable names without
  containing usable secrets.
- `prometheus-console.yml.example` is a same-host scrape fragment for the
  loopback-only `/metrics` endpoint; install it only in the monitoring network.
- `scripts/production_network_preflight.py` performs the final read-only public
  check for approved DNS resolution, certificate hostname validation, frontend
  reachability, API liveness/readiness and required browser security headers.
  It never sends credentials or changes DNS, Nginx, FRP or service state.

The exact rollout and validation order is documented in
`docs/operations/console-deployment.md`.
