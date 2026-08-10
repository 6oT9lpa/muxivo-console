# Service boundaries

## Console responsibilities

Muxivo Console is a control plane, not a bot runtime.

It owns:

- first-party user accounts, sessions and linked sign-in identities;
- organizations, memberships and platform-neutral RBAC;
- connection registry and non-secret adapter metadata;
- aggregated navigation, audit presentation and account preferences;
- authorization to call platform Control APIs.

It does not own:

- Twitch EventSub processing, moderation actions, rate limiting or bot tokens;
- Discord gateway processing, bot tokens or Discord-specific role truth;
- Muxivo Core model execution, training data or moderation decision truth;
- raw platform events except an intentionally minimized cross-service audit
  projection.

## Platform service responsibilities

Each platform service remains the source of truth for its own configuration and
credentials.

```text
Muxivo Console API
  -> Twitch Control API       (commands, policies, review queue, connection health)
  -> Discord Control API      (Discord-specific modules)
  -> Muxivo Core internal API (only through platform services where possible)
```

Console must use versioned service APIs and service-to-service credentials. It
must not query a platform service's database directly.

## API boundary

The Console web app communicates only with the Console API (BFF). The BFF adds
the authenticated actor and selected organization context after validating the
first-party session. It invokes a platform Control API with a short-lived
service assertion containing:

- actor ID;
- organization ID;
- requested resource and action;
- correlation ID;
- expiry;
- audience bound to the target service.

The platform service independently authorizes the assertion and verifies that
the requested resource is attached to the stated organization.

## Proposed repository layout

```text
muxivo Console/
  apps/
    api/                 # FastAPI BFF and identity/control plane
    web/                 # Vue + TypeScript Console UI
  packages/
    ui/                  # reused design system from Discord Activity
    contracts/           # versioned API types, no business logic
  docs/
  tests/

muxivo Twitch/
  src/
    domain/
    application/
    infrastructure/
    presentation/
  migrations/
  tests/
```

The Console API follows the existing Muxivo Python/FastAPI and dependency
injection conventions. Its domain and application layers must depend on ports,
not on HTTP/OAuth SDK/database implementations.
