# Identity and access architecture

## Decision

Muxivo Console has one first-party account model. A login method proves who the
person is; it does **not** grant control over Twitch, Discord or another adapter.
Platform control is granted only by a separate, explicit and revocable adapter
connection after ownership and platform permissions have been verified.

This prevents an unsafe coupling such as "signed in with Discord, therefore may
control every Twitch bot linked to the same email address".

## Terms

| Term | Meaning |
| --- | --- |
| `User` | A first-party Muxivo account. |
| `LoginIdentity` | A verified way to sign in: password/email, Twitch, Discord, Google or Yandex ID. |
| `Organization` | A tenant that owns integrations and settings. A single creator normally receives one personal organization. |
| `Membership` | A user's role in an organization. |
| `PlatformConnection` | An explicit authorization of a platform resource, e.g. a Twitch broadcaster channel or Discord guild. |
| `AdapterCredential` | Encrypted platform tokens and metadata used only by the owning platform service. |
| `ActivitySession` | A short-lived Discord-Activity-only session, scoped to one guild and Discord modules. |

## Account model

```text
User 1 --- * LoginIdentity
User * --- * Organization through Membership
Organization 1 --- * PlatformConnection
PlatformConnection 1 --- * AdapterCredential history
```

`LoginIdentity` and `PlatformConnection` must remain separate tables and
separate concepts.

Examples:

| How the person signs in | What they may do immediately | What requires an additional connection |
| --- | --- | --- |
| Email and password / magic link | Use Muxivo Console and create an organization | Connect Twitch, Discord or another adapter |
| Google / Yandex ID | Use Muxivo Console and create or join an organization | Connect any bot adapter |
| Twitch login | Use Muxivo Console as a person | Explicitly authorize a broadcaster/channel connection and requested bot scopes |
| Discord login | Use Muxivo Console as a person | Explicitly authorize a Discord guild connection or join an organization |
| Discord Activity launch | Use only the existing Discord Activity in its current guild context | Nothing outside Discord Activity |

## Browser authentication

### Supported identity providers

1. Email: password plus recovery/session safety. New e-mail/password accounts
   must prove inbox ownership with the short-lived verification flow before
   their user, login identity and password credential become active.
2. OIDC/OAuth providers: Twitch, Discord, Google and Yandex ID.
3. Future enterprise OIDC/SAML providers without changing the user model.

Every social provider uses Authorization Code Flow with PKCE, an allowlisted
redirect URI, a one-time `state`, nonce validation where supported and a strict
provider-to-subject uniqueness constraint.

The Console creates a first-party browser session only after the provider
identity has been verified. Sessions are stored server-side and represented in
the browser by a Secure, HttpOnly, SameSite cookie. The browser does not receive
platform refresh tokens.

### E-mail registration trust boundary

The e-mail/password registration flow is deliberately split into two
application steps:

1. `POST /api/v1/auth/email-password/registrations` validates the input,
   encrypts the normalized e-mail, hashes the password with Argon2id, hashes
   the six-digit code and stores only that pending representation in the
   short-lived Redis token store. The endpoint returns an opaque pending-flow
   token and never creates a user account.
2. `POST /api/v1/auth/email-password/registration-verifications` verifies the
   code with a constant-time comparison and atomically consumes the pending
   value. Only then does the transactional writer create the user, e-mail
   identity, password credential and audit event.

The resend endpoint rotates the code and retains the same short-lived pending
flow. Delivery failures fail closed and remove the pending value so an
unusable or partially delivered registration cannot become an accidental
account-creation path. Existing e-mail addresses use the same generic public
response and are never enumerated.

### Identity linking rules

- Do not merge accounts solely because providers return the same email address.
- Linking a new login identity requires an already authenticated Muxivo session
  and a fresh authentication challenge for the provider being linked.
- Removing the final usable login identity is forbidden.
- Recovery and sensitive account changes require recent authentication; future
  email-address changes should use the same verified-email trust boundary.
- A user may link several identities of the same provider only if that becomes
  a product requirement; the initial UI should expose one primary identity per
  provider to reduce confusion.

## Adapter connections

Adapter connections are initiated from a selected organization, never as an
implicit side effect of sign-in.

### Twitch

The user selects **Connect Twitch channel**. Console asks the Twitch Control API
for a browser-safe list of channels available to the linked broadcaster
identity, so the user never pastes a channel ID. The Twitch consent screen
requests only the scopes required by the enabled capabilities. The backend
verifies the authorized Twitch user and the selected broadcaster resource,
creates the connection in `PENDING`, performs bot/EventSub/moderator preflight
checks and only then activates it.

### Discord

The user selects **Connect Discord server**. Console asks the Discord Control
API for a browser-safe list of servers available to the linked Discord identity,
so the user never pastes a guild ID. The Console then verifies that the user
has the required guild authority, that the Muxivo Discord bot is installed and
that the selected guild is not already attached to another organization unless
an explicit transfer process is completed.

### Credential ownership

Console may keep connection status and non-secret metadata. Encrypted OAuth
credentials belong to the platform service that uses them:

```text
Console: connection_id, organization_id, platform, external_resource_id, status
Twitch service: encrypted Twitch tokens, granted scopes, refresh metadata
Discord service: encrypted Discord credentials when they are needed
```

This avoids a shared token database and constrains a compromise of one service.

## Authorization model

Authorization is resource-based. A role answers *what* a member can do inside
an organization; a policy check answers *where* that action is valid.

Initial organization roles:

| Role | Capabilities |
| --- | --- |
| `OWNER` | Full control, ownership transfer, billing, adapter removal and data deletion. |
| `ADMIN` | Manage members, policies, automations and integrations, but not ownership transfer. |
| `MODERATOR` | Read moderation data and resolve review items on assigned resources. |
| `ANALYST` | Read-only metrics, logs and reports. |
| `VIEWER` | Explicitly granted read-only access to selected modules. |

Every policy check uses `(actor, organization, resource, action)`. No route may
authorize access from a client-supplied `guild_id`, `broadcaster_id` or role
name alone.

## Discord Activity trust path

Discord Activity is not a browser Console login.

1. The Activity SDK obtains a short-lived Discord authorization code with
   `prompt=none` inside Discord.
2. The existing Discord Activity backend exchanges and validates it.
3. It derives the guild context from the trusted SDK/server interaction,
   synchronizes or verifies Discord roles and returns a short-lived,
   audience-restricted Activity session.
4. The session includes only Discord-scoped claims: `platform=discord`,
   `guild_id`, allowed Discord modules and expiration.
5. The token is accepted only by Discord Activity endpoints. It cannot be
   exchanged for a Console browser cookie and cannot call Twitch endpoints.

The Activity may include a **Open Muxivo Console** button. It starts a fresh
browser OAuth/login session and never forwards the Activity bearer token.

## Minimum security controls

- Secure, HttpOnly session cookies; CSRF protection for all mutations.
- Server-side session revocation, rotation after sign-in and recent-auth checks
  for sensitive actions.
- Passwords hashed with Argon2id; no reversible password storage.
- OAuth `state` values are single-use, short-lived and bound to provider,
  redirect URI, browser session and requested operation (`login`, `link`, or
  `connect_adapter`).
- Encrypt credentials with envelope encryption and rotate keys.
- Audit sign-in, linking, unlinking, connection, disconnection, role and policy
  mutations; redact secrets and personal content from logs.
- Rate-limit login, callback, recovery and token-refresh paths.
- Use a generic public error for account discovery-sensitive flows.

## Invariants

1. A login identity never implies ownership of an adapter resource.
2. An adapter credential never reaches a browser, Console API response or log.
3. A Discord Activity session is never valid at a browser Console or Twitch API.
4. A user can never grant themselves a role above their own organization role.
5. Deactivation or revocation of a platform connection immediately blocks new
   platform actions.
