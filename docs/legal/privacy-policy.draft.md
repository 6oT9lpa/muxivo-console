# Muxivo Console Privacy Policy — Draft

This is a product-specific draft for legal review. It is not legal advice and
must not be published until the responsible Muxivo legal entity, hosting
region, subprocessors, contact channel and launch jurisdictions are confirmed.

## Controller and contact

- Legal entity: `TBD`
- Registered address: `TBD`
- Privacy contact: `TBD`
- Data protection contact, if required: `TBD`

## Data we process

Muxivo Console processes the minimum data needed to provide the control plane:

- account email address and display name;
- password-derived credential material, never a plaintext password;
- first-party browser session records, timestamps and privacy-preserving
  presentations of IP address and user agent;
- linked Discord/Twitch identity subjects, without provider access or refresh
  tokens in Console;
- organization names, memberships, roles and scoped permissions;
- platform connection metadata, including platform, resource identifier,
  lifecycle status and non-secret health metadata;
- security and administrative audit events;
- support, deletion and access-request information supplied by the requester.

Console must not store Discord/Twitch access tokens, refresh tokens, bot tokens,
provider authorization codes or platform runtime moderation data. Those remain
owned by the relevant platform service.

## Purposes and legal basis

The final published version must map each purpose to the applicable legal basis
for each launch jurisdiction. The intended purposes are:

- authenticate users and maintain secure sessions;
- provide organization membership, RBAC and platform connection controls;
- detect abuse, protect the service and investigate security incidents;
- maintain auditability for administrative and security-sensitive actions;
- answer support, access, correction, export and deletion requests.

The legal basis mapping is `TBD` and requires legal review.

## Sharing and subprocessors

The final list must identify each provider, processing purpose, region and
contractual basis:

- hosting provider: `TBD`;
- database provider: `TBD`;
- SMTP.BZ: recovery-mail delivery provider; processing region and contractual
  terms require confirmation before publication;
- monitoring, metrics and error provider: `TBD`;
- HashiCorp Vault: selected secret-manager/KMS boundary; deployment region and
  contractual terms require confirmation before publication.

No provider may receive Console secrets through frontend code or unredacted
application logs.

## Retention and deletion

The operational baseline is documented in
[`retention-policy.md`](../operations/retention-policy.md). Legal holds and
jurisdiction-specific requirements override the baseline only for the records
covered by the hold or requirement.

## Security

Subject to the final deployment being configured as documented, Console uses
HttpOnly session cookies, CSRF protection, rate limiting, secure browser
headers, recent-authentication gates, hashed security tokens, secret-redacted
structured logs and audit events for sensitive changes. These statements must
be reviewed against the actual staging deployment before publication.

## User rights and requests

The final request channel is `TBD`. The process must support, as applicable:

- access and export;
- correction;
- deletion;
- restriction or objection;
- organization and connection revocation requests.

Requester verification must not require sending passwords or provider tokens by
email. The incident and request handling procedures are documented in the
operations artifacts and require owner/legal approval before launch.

## Changes and publication

Effective date, revision history, cookie notice and jurisdiction-specific
supplements are `TBD`. Publish only after legal review and after the listed
subprocessors and contact channels are real.
