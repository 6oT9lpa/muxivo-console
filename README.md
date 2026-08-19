# Muxivo Console

`Muxivo Console` is the platform-neutral control plane for the Muxivo ecosystem.

It provides a single Muxivo account, browser sessions, organization-level access
control and a secure way to connect platform adapters such as Twitch and Discord.
It never owns a platform bot's runtime work, moderation decisions or platform
database records. Those remain the responsibility of the relevant platform
service and Muxivo Core.

## Initial scope

- Browser sign-in through email, Twitch, Discord, Google and Yandex ID.
- Explicit, revocable connections to Discord and Twitch adapters.
- A platform-neutral organization/workspace and RBAC model.
- A protected control API for the Console web application.
- A restricted Discord Activity trust path that exposes Discord-only resources.

## Documents

- [Identity and access architecture](docs/architecture/identity-and-access.md)
- [Service boundaries](docs/architecture/service-boundaries.md)
- [Implementation roadmap](docs/architecture/implementation-roadmap.md)
- [Discord Activity extraction: first migration slice](docs/architecture/discord-activity-extraction.md)

## First implementation slice

The repository now contains the first backend boundary in `apps/api`:

- a versioned, platform-neutral `ControlModule` contract;
- a clean-architecture use case that authorizes before calling a platform port;
- a fail-closed FastAPI route: `GET /api/v1/organizations/{organization_id}/control-modules`;
- tests proving that an unauthorized request cannot invoke a platform adapter.

The supplied `StaticModuleCatalog` is a deliberately temporary development
adapter. It proves the contract without accessing the Discord database. Replace
it only with a signed, versioned Discord Control API adapter after Console
first-party sessions and organization RBAC are wired.

## Non-goals for the first implementation

- Replacing the existing Discord Activity in one migration.
- Storing Twitch, Discord or any other platform access tokens in the browser.
- Giving a social-login provider implicit access to a platform adapter.
- Making a Twitch Extension the source of truth for protected configuration.

## Local development walkthrough

The repository provides a localhost-only walkthrough for the real Console BFF,
its database migrations and the Vue browser application. It intentionally uses
a separate development ASGI entrypoint and does not weaken production cookie
policy or use production credentials.

Requirements: Docker Desktop, Python 3.12, Node.js and installed dependencies.
For a fresh clone:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
Push-Location apps\web; npm install; Pop-Location
```

```powershell
Set-Location 'E:\muxivo\muxivo Console'
.\scripts\start-dev.ps1
```

Open `http://127.0.0.1:5173` and sign in with
`demo@example.com` / `muxivo-demo-password`. Create an organization and use
the workspace controls. The script creates its random development-only keys in
the ignored `.dev/console.env` file and starts PostgreSQL, the API and Vite.

The walkthrough exercises Console-owned authentication, organization and RBAC
flows. Browser operations that read a connected Discord guild still require the
real Discord Control API to be running on `http://127.0.0.1:8030`; the local
walkthrough never pretends to have a Discord identity or administrator access.

Stop the processes with:

```powershell
.\scripts\stop-dev.ps1
```
