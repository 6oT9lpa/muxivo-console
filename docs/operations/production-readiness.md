# Muxivo Console production readiness

Status: draft for staging preparation. This document is not legal advice and must
be reviewed by counsel before public launch.

Canonical supporting artifacts:

- [`privacy-policy.draft.md`](../legal/privacy-policy.draft.md)
- [`terms-of-service.draft.md`](../legal/terms-of-service.draft.md)
- [`data-inventory.md`](data-inventory.md)
- [`retention-policy.md`](retention-policy.md)
- [`incident-runbook.md`](incident-runbook.md)

## External references used for this draft

- FTC business guidance on privacy and security:
  https://www.ftc.gov/business-guidance/privacy-security
- FTC guide to protecting personal information:
  https://www.ftc.gov/business-guidance/resources/protecting-personal-information-guide-business
- European Commission GDPR legal framework:
  https://commission.europa.eu/law/law-topic/data-protection/legal-framework-eu-data-protection_en

## Launch gates

Muxivo Console is not public-production ready until every required gate below is
completed.

| Area | Gate | Status |
| --- | --- | --- |
| Identity | E-mail/password registration creates an account only after a short-lived six-digit code is verified | Implemented; SMTP.BZ secret-manager wiring and delivery test pending |
| Identity | Password recovery SMTP delivery adapter configured outside logs | SMTP.BZ domain verified and STARTTLS/AUTH probe passed; secret-manager wiring and delivery test pending |
| Security | Shared rate limits enabled for login, registration, reauthentication, OAuth callback and recovery | Redis is installed and loopback-only; staging secret-manager URL wiring pending |
| Security | CORS allowlist configured for staging/prod origins | Enforced in settings; values pending |
| Security | CSP, HSTS and browser hardening headers enabled | Implemented |
| Security | Secret redaction filter and structured JSON logging installed in production composition | Implemented |
| Security | Browser contracts checked for platform token exposure | Implemented in CI |
| Security | Secret scan in CI | Implemented |
| Security | Audit coverage review for sensitive Foundation actions | Implemented in CI |
| Security | Recent authentication refresh and gates for password change, identity unlink and sensitive writes | Implemented |
| Security | Scheduled cleanup for expired sessions and recovery transactions | Implemented |
| Observability | `/metrics` scraped and alert rules configured | Metrics endpoint and alert rules implemented; scraper backend pending |
| Operations | Liveness/readiness endpoints distinguish process health from database readiness | Implemented; staging API service/env wiring and external monitor pending |
| Lifecycle | Periodic platform connection reconciliation worker | Implemented |
| Lifecycle | Idempotency keys for retry-safe lifecycle actions | Implemented |
| Lifecycle | Browser-safe platform resource candidate discovery | Console contract/UI implemented; Control API endpoints pending |
| Lifecycle | Discord/Twitch ownership verification before registration | Implemented; Twitch Control API config pending |
| Lifecycle | Discord/Twitch browser-safe connection health adapters | Implemented; Twitch Control API config pending |
| Lifecycle | Discord token/scope reconciliation contract | Implemented |
| Lifecycle | Twitch token/scope reconciliation contract | Implemented; service URL/signing key pending |
| Quality | Production composition smoke with fail-fast env checks | Implemented in CI |
| Quality | Development Docker Compose smoke | Implemented in CI |
| Compliance | Privacy policy reviewed and published | Pending legal review |
| Compliance | Terms reviewed and published | Pending legal review |
| Compliance | Data inventory and retention schedule approved | Draft |
| Operations | Incident runbook approved and exercised | Draft |
| Operations | Backup/restore drill completed | Drill procedure documented; staging exercise pending |
| Deployment | Staging/prod domains provisioned | Temporary staging `beget.ame-life.com` is active; canonical production host pending |
| Deployment | Staging/prod OAuth credentials provisioned | Discord/Twitch OAuth enforced; values pending |
| Secrets | KMS/secret manager selected and wired | Secret-manager source enforced; provider pending |

E-mail ownership verification is part of the current Console authentication
flow. The public registration endpoint creates only a short-lived pending
record, stores encrypted/hashed values in the one-time token store, and sends
the six-digit code through the configured SMTP adapter. The user account,
password credential and registration audit event are created only after the
code is verified. SMTP configuration and a real recipient delivery check still
remain staging/prod launch gates.

## Privacy policy draft outline

The published privacy policy must be specific to the final Muxivo legal entity,
hosting region, subprocessors and launch jurisdictions. Use this outline as the
source checklist.

### Data we collect

- Account data: email address, display name and login identity provider IDs.
- Authentication data: server-side browser session records, session timestamps,
  hashed session tokens, hashed IP presentation and hashed user-agent
  presentation.
- Organization data: organization name, slug, memberships, roles and scoped
  permissions.
- Platform connection metadata: connected platform, external resource ID,
  connection status and non-secret health metadata.
- Audit events: actor ID, organization ID, action, target type, target ID,
  status and timestamp.
- Support and deletion request data: messages sent to support and request
  verification artifacts.

Muxivo Console must not store platform access tokens, refresh tokens, bot tokens
or platform runtime moderation data. Those belong to the relevant platform
service.

### How we use data

- Provide account authentication and organization access.
- Allow owners/admins to connect and manage platform resources.
- Enforce RBAC, scoped permissions and security checks.
- Detect abuse, troubleshoot service health and investigate security incidents.
- Maintain audit records for security and administrative accountability.

### Sharing and subprocessors

Before staging, fill in actual subprocessors:

- Hosting provider: TBD.
- Database provider: TBD.
- Email delivery provider for verification/recovery: SMTP.BZ domain verification and non-delivery authentication probe passed; production secret-manager wiring and approved delivery test pending.
- Error/metrics/logging provider: TBD.
- KMS/secret manager provider: TBD.

### User rights and requests

Publish a request channel before launch, for example
`privacy@muxivo.example`. The process must support:

- access/export requests;
- correction requests;
- account deletion requests;
- organization deletion requests by authorized owner;
- platform connection revocation requests.

### Security statement

The policy may state only controls that are actually implemented. As of this
draft, Console can accurately describe:

- server-side browser sessions with HttpOnly cookies;
- CSRF protection for authenticated mutations;
- rate limiting for abuse-prone authentication and reauthentication flows;
- production browser security headers;
- hashed browser session and recovery tokens;
- recent authentication refresh plus gates for password change, login identity
  unlink and sensitive platform writes;
- secret redaction for logs;
- audit logging for sensitive organization, identity, session and connection
  lifecycle changes.

Do not promise certifications, encryption details, availability targets or
incident notification timelines until they are approved and operationally true.

## Terms draft outline

The published terms must be reviewed by counsel. Product-specific clauses should
cover:

- Muxivo Console account ownership and acceptable use.
- Organization ownership, member responsibility and role assignment.
- Requirement that a user may connect only platform resources they are
  authorized to administer.
- Revocation rights: Muxivo may revoke connections or suspend accounts for
  abuse, security risk or loss of platform authorization.
- Separation of responsibilities between Muxivo Console and platform services.
- Beta/staging disclaimer until public production.
- Limitations around third-party platform availability and API changes.
- User responsibility for complying with Discord/Twitch/community rules.
- Data deletion and export process references.

## Data inventory

| Data class | Stored in Console | Secret? | Browser exposed? | Notes |
| --- | --- | --- | --- | --- |
| User ID | Yes | No | Yes, indirectly through authorized responses only if needed | First-party account identifier |
| Email address | Protected/encrypted | Personal data | No normal response exposure | Lookup hash used for login |
| Password hash | Yes | Secret-derived | Never | Argon2id hash only |
| Browser session token | Hash only | Yes | Cookie carries raw opaque token, HttpOnly | DB never stores raw token |
| CSRF token | Cookie + header | Security token | Yes, intentionally browser-readable | Not an authentication credential |
| Recovery token | Hash only | Yes | Only delivered through recovery channel | Logs must never include raw token |
| Login identity provider subject | Yes | Personal/provider metadata | Limited identity profile only | No provider OAuth token |
| Organization | Yes | No | Yes to members | Tenant boundary |
| Membership role/scopes | Yes | No | Yes to authorized members | Used for RBAC |
| Platform connection resource ID | Yes | Platform metadata | Yes to authorized members | Not a credential |
| Platform access/refresh token | No | Yes | Never | Owned by platform service |
| Audit events | Yes | Security metadata | Yes to authorized members | Secret-free event facts |
| Logs | Yes, provider TBD | May contain metadata | No | Redaction required |
| Metrics | Yes, provider TBD | No secrets | No | Aggregated counters/durations |

## Retention policy draft

| Data | Default retention | Deletion trigger |
| --- | --- | --- |
| Active user account | While account is active | Account deletion request |
| Password credentials | While email identity is usable | Identity removal/account deletion |
| Revoked/expired sessions | 30 days | Scheduled cleanup |
| Password recovery transactions | 24 hours after expiry/consumption | Scheduled cleanup |
| Organization records | While organization exists | Owner-approved organization deletion |
| Membership records | While membership is active, then 1 year in audit | Member removal/account deletion |
| Platform connection metadata | While connection exists, then 1 year in audit | Disconnect/revoke/delete request |
| Audit events | 1 year minimum, final period TBD with counsel | Retention expiry |
| Application logs | 30 to 90 days, final period TBD | Retention expiry |
| Metrics | 90 days aggregated, final period TBD | Retention expiry |
| Backups | 30 days for daily backups, final period TBD | Backup expiry |

Scheduled cleanup jobs enforce the session and password recovery windows above.
Before launch, map the table into backup retention settings as well. If legal
hold applies, deletion must pause only for the
specific records under hold.

## Revoke/delete request procedure

### Platform connection revoke

1. Verify requester identity and organization role.
2. Require recent authentication for owner/admin destructive actions.
3. Mark connection `DISCONNECTED` or execute revoke workflow when platform
   credentials exist in the platform service.
4. Record audit event with actor, organization, connection and result.
5. Confirm completion to the requester without exposing platform tokens.

### Account deletion

1. Verify requester identity and recent authentication.
2. Confirm whether the account owns organizations.
3. If the user is sole owner, require ownership transfer or organization
   deletion approval.
4. Revoke active browser sessions.
5. Remove or anonymize login identities and personal account data according to
   the approved retention schedule.
6. Preserve minimal audit records if required by security/legal retention.
7. Send completion confirmation through the approved support channel.

### Organization deletion

1. Verify requester is organization owner.
2. Require recent authentication.
3. Disconnect/revoke all platform connections.
4. Remove memberships and organization metadata.
5. Preserve secret-free audit records according to retention schedule.
6. Document backup deletion timing.

## Incident runbook

### Severity levels

| Severity | Definition | Initial response |
| --- | --- | --- |
| SEV-1 | Confirmed credential/token exposure, active compromise or data exfiltration | Page owner immediately, freeze deploys, rotate secrets |
| SEV-2 | Authentication bypass, privilege escalation or widespread outage | Page owner within 15 minutes |
| SEV-3 | Limited security defect or degraded adapter lifecycle | Triage within business day |

### First hour checklist

1. Assign incident commander and scribe.
2. Capture timeline in an incident document.
3. Preserve logs, audit events and deployment SHAs.
4. Identify blast radius: users, organizations, platform connections and data
   classes affected.
5. Stop ongoing exposure: revoke sessions, disable risky routes, rotate secrets
   or disconnect affected platform connections.
6. Prepare internal status update.
7. Decide notification obligations with counsel.

### Recovery checklist

1. Patch root cause.
2. Add regression tests or detection.
3. Rotate affected credentials.
4. Re-enable services through a staged rollout.
5. Complete post-incident review with action owners and due dates.

## Alerting plan

Wire `/metrics` into the selected monitoring backend using
[`deploy/prometheus-console.yml.example`](../../deploy/prometheus-console.yml.example)
as the same-host scrape reference, then load
`docs/operations/prometheus-alerts.yml`. The API binds to loopback and the
Nginx configuration keeps `/metrics` out of the public browser surface. Minimum
alerts:

- high 5xx rate over 5 minutes;
- sustained p95 latency above target;
- login/register/recovery rate-limit denial spike;
- password recovery/authentication failure spike;
- connection lifecycle failures by status/action;
- no metrics scraped for more than 5 minutes in production.

## Domain and OAuth checklist

Before staging:

- choose staging Console domain;
- choose production Console domain;
- configure `MUXIVO_CONSOLE_PUBLIC_BASE_URL` for each environment;
- configure `MUXIVO_CONSOLE_CORS_ALLOWED_ORIGINS` for both domains; the allowlist
  must include `MUXIVO_CONSOLE_PUBLIC_BASE_URL`;
- configure CSP `connect-src` for API origins;
- create staging Discord OAuth application credentials;
- create production Discord OAuth application credentials;
- create staging Twitch OAuth application credentials;
- create production Twitch OAuth application credentials;
- configure exact Discord redirect URI per environment:
  `/api/v1/auth/discord/callback`;
- configure exact Twitch redirect URI per environment:
  `/api/v1/auth/twitch/callback`;
- store OAuth client secrets in the selected secret manager only.

## KMS/secret manager decision

Production must not use `.env` as the secret source of truth. `.env` is allowed
only for local development. Outside development, Console settings fail fast
unless `MUXIVO_CONSOLE_SECRET_SOURCE` names an approved secret manager.

Decision options:

| Option | Pros | Cons |
| --- | --- | --- |
| Cloud provider KMS + Secret Manager | Managed rotation/audit/IAM | Ties deployment to provider |
| HashiCorp Vault | Portable and mature | More operations burden |
| Doppler/1Password Secrets Automation | Fast setup | External vendor dependency |

Required capabilities:

- per-environment secret namespaces;
- IAM or workload identity, not long-lived machine credentials;
- access audit logs;
- rotation process for OAuth, session pepper, encryption keys and signing keys;
- emergency revoke path;
- no secret values printed in app logs, CI logs or frontend bundles.

Accepted `MUXIVO_CONSOLE_SECRET_SOURCE` values are:

- `aws-secrets-manager`;
- `azure-key-vault`;
- `doppler`;
- `gcp-secret-manager`;
- `hashicorp-vault`;
- `kubernetes-secrets`;
- `onepassword-secrets-automation`.

## Backup/restore drill

Minimum documented drill before production:

1. Create encrypted database backup from staging.
2. Restore into isolated environment.
3. Run migrations forward.
4. Run one rollback migration test for the newest migration.
5. Verify account login, organization list, member list, platform connection
   list and audit timeline from restored data.
6. Verify recovery from backup does not restore revoked active sessions as
   usable sessions.
7. Record restore time objective, data loss window and any manual steps.

## Remaining engineering follow-up

- Wire the installed loopback Redis service into the staging secret-manager
  environment, then provision the shared edge rate-limit backend for prod.
- Implement the signed `/connection-candidates` endpoint in each platform
  Control API and validate it against the contract in the Console deployment
  runbook.
- Configure Twitch Control API service URL and signing key in staging/prod.
- Store the verified SMTP.BZ credential in the staging/prod secret manager and run one explicitly approved recovery delivery test.
- Load `docs/operations/prometheus-alerts.yml` into the selected metrics backend.
- Expand Discord/Twitch contract tests against live sandbox Control API fixtures
  once those services expose staging endpoints.
