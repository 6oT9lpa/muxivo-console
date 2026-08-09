# Authorization policy contract

## Decision

Console application use cases authorize a complete, typed request before they
call an adapter. A request always contains:

- `actor_id` — the first-party Muxivo user resolved from a browser session;
- `organization_id` — the tenant context chosen by the server-side session;
- `resource` — a platform-neutral Console resource;
- `action` — the requested operation.

`OrganizationAuthorizer` is the inbound application port for that decision.
Its default development implementation denies every request. Production will
implement this port with memberships and scoped grants; no HTTP route or
platform adapter may bypass it.

## Current first resource

`GET /api/v1/organizations/{organization_id}/control-modules` requests
`resource=console.control_modules` and `action=read`.

Console makes this decision before it calls `ModuleCatalog`. The receiving
platform service must still check the service assertion, connection ownership,
and any native authority it needs. A Console allow is therefore necessary but
not sufficient for a platform action.

## Extension rule

New use cases must add an explicit resource/action pair instead of deriving
authorization from a route name, client-supplied platform ID, or a global role
string. This preserves the roadmap invariant: actor + organization + resource
+ action are checked on the backend for every mutation and read boundary.
