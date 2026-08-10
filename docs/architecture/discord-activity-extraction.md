# Discord Activity extraction: first migration slice

## Decision

Muxivo Console exposes browser control surfaces through a platform-neutral
`ControlModule` contract. The Console does not import Discord Activity's session,
Pinia store, roles, database models, or bearer token. The Discord service remains
the owner of Discord runtime, guild authority, Discord-specific RBAC and all
Discord credentials.

## First slice

`GET /api/v1/organizations/{organization_id}/control-modules` is the Console's
read-only module registry. It intentionally returns a small common vocabulary:

- a stable namespaced module key, such as `discord.logs`;
- the owning platform;
- the capability granted by the platform Control API;
- an availability status that can safely appear in the browser.

The actual production `ModuleCatalog` adapter will call a versioned Discord
Control API using a short-lived service assertion containing actor,
organization, resource/action, correlation ID, expiration and Discord audience.
It must never read Discord tables directly.

## Security boundary

The existing Activity session remains `audience=discord-activity`, guild-scoped
and accepted only by Discord Activity endpoints. The `Open Muxivo Console` button
must create a new browser sign-in flow; it must not pass an Activity access token
in URL, cookie, local storage, referrer, or request body.

Console authorization is evaluated before the platform adapter is called. The
platform still verifies its own resource ownership and native authority. Thus an
effective allow decision requires both Console authorization and platform
authorization.

## Migration sequence

1. Implement first-party Console sessions and organization memberships.
2. Replace `StaticModuleCatalog` with a signed `DiscordControlApiCatalog`.
3. Add an `Open Console` browser-login entry point to Activity without touching
   Activity token issuance.
4. Move a read-only module (recommended: audit/logs) behind the contract; retain
   the Activity page until parity, access and rollback checks pass.
5. Migrate mutations one module at a time with idempotency keys, audit events and
   an explicit Discord-side authorization check.

## Non-goals of this slice

- no token sharing between Activity and Console;
- no change to Discord-native access roles;
- no direct database coupling;
- no migration of bot runtime work into Console.
