# Muxivo Console deployment artifacts

These files describe an isolated deployment of Muxivo Console beside the
existing Discord Activity. The existing Activity keeps its current public host,
local port and FRP proxy. Console uses its own local API port `8010`, FRP port
`18081` and host `console.muxivo.pro`.

Do not copy credentials from the examples into Git. The production environment
must be rendered by the selected secret manager and loaded through the systemd
credential path used by `muxivo-console-api.service`.

- `muxivo-console-api.service` runs the production ASGI application and applies
  migrations before startup.
- `frpc-console.toml.example` is only a proxy fragment. Merge the `[[proxies]]`
  block into the existing `/etc/frp/frpc.toml` while preserving its server and
  authentication settings.
- `nginx-console-bootstrap.conf.example` serves the HTTP/ACME bootstrap host.
- `nginx-console.conf.example` is the final HTTPS virtual host.
- `console.env.example` documents the required production variable names without
  containing usable secrets.
- `prometheus-console.yml.example` is a same-host scrape fragment for the
  loopback-only `/metrics` endpoint; install it only in the monitoring network.

The exact rollout and validation order is documented in
`docs/operations/console-deployment.md`.
