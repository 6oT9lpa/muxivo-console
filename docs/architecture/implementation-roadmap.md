# Muxivo Console implementation roadmap

## Phase A — foundation

1. Create FastAPI and Vue/TypeScript applications using the stated layout.
2. Add PostgreSQL migrations for users, login identities, organizations,
   memberships, sessions, adapter connections and append-only audit records.
3. Implement password registration, session rotation, logout and account
   recovery with secure error handling. Verified-email confirmation is excluded
   from this Foundation pass and belongs to a later account-trust milestone.
4. Implement RBAC policy checks and organization selection.
5. Add health/readiness endpoints, structured logs, correlation IDs, metrics,
   CI, unit tests and security tests.

Exit gate: email-based account creation and organization membership work without
any platform token in the browser.

## Phase B — browser identity providers

1. Implement provider-port interfaces and OAuth/OIDC adapters for Discord,
   Twitch, Google and Yandex ID.
2. Add link/unlink and recent-auth flows.
3. Add connection and session audit records.
4. Test account-takeover cases: conflicting emails, stale state, callback replay
   and provider unlinking.

Exit gate: every provider is a login identity only; none grants adapter control
without an explicit connection flow.

## Phase C — Twitch Control API integration

1. Define versioned Console-to-Twitch contracts.
2. Build Twitch channel connection wizard and preflight state machine.
3. Present Twitch runtime health, granted scopes and reauthorization state.
4. Add Twitch commands and moderation pages as the Twitch service exposes them.

Exit gate: a Console user can connect, monitor and revoke one Twitch channel
while credentials remain inside the Twitch service.

## Phase D — Discord migration path

1. Extract reusable Vue UI components and API-client conventions from Discord
   Activity into `packages/ui` and `packages/contracts`.
2. Preserve current Activity behavior and its Discord-only activity session.
3. Implement "Open Console" as a fresh browser login, never an Activity token
   hand-off.
4. Migrate selected generic pages incrementally after parity and access tests.

Exit gate: Discord Activity remains functional throughout; Console migration is
reversible and does not broaden Activity permissions.

## Phase E — optional Twitch Extension

Implement only after Console and Twitch runtime are stable. The Extension is a
companion for safe read-only viewer information and compact broadcaster control;
Console remains the source of truth for protected settings.
