# Muxivo Console Data Inventory — Draft

This inventory is an operational draft. Replace `TBD` values with the actual
provider, region, retention configuration and owner before staging approval.

| Data class | Stored by Console | Secret/personal data | Browser exposure | Primary purpose | Retention |
| --- | --- | --- | --- | --- | --- |
| User account | User ID, email ciphertext, display name, status | Personal; email protected | Authorized account context only | Authentication and ownership | While account exists; deletion procedure applies |
| Password credential | Argon2id password hash and credential metadata | Secret-derived | Never | Password authentication | While identity is usable |
| Browser session | Hashed session token, timestamps, assurance, hashed IP/user-agent presentation | Security metadata | Raw opaque session cookie only; HttpOnly | Session security | 30 days after expiry/revocation |
| CSRF token | Browser cookie and request header value | Security token | Intentionally readable by browser | CSRF defense | Session lifetime |
| Pending registration | Registration ID, encrypted e-mail, keyed e-mail lookup hash, Argon2id password hash, keyed code hash and bounded attempts | Personal/security metadata | Opaque pending-flow token and user-entered code only; raw password/code never persisted | E-mail ownership verification before account creation | Short-lived Redis TTL; delete on verification or delivery failure |
| Recovery transaction | Hashed recovery token, expiry and user reference | Security metadata | Raw token only through approved recovery channel | Password recovery | 24 hours after expiry/consumption |
| Login identity | Provider and provider subject | Provider metadata | Limited profile projection | Sign-in and identity linking | While identity is linked |
| Organization | Name, slug and identifiers | Tenant metadata | Authorized organization responses | Tenant boundary | While organization exists |
| Membership | Role and resource scopes | Access-control metadata | Authorized members | RBAC | While active; audit retention after removal |
| Platform connection | Platform, external resource ID, state, scopes and health metadata | Platform metadata | Authorized members; no credentials | Connection control plane | While connected; audit retention after revoke |
| Audit event | Actor, organization, action, target, outcome, timestamp and correlation ID | Security metadata | Authorized members only | Accountability and incident response | Minimum 1 year, final period `TBD` |
| Application logs | Redacted structured operational metadata | May contain metadata | Never | Debugging and incidents | 30–90 days, final period `TBD` |
| Metrics | Aggregated counters and durations | No intended personal data | Monitoring network only | Alerting and capacity | 90 days aggregated, final period `TBD` |

Console must not persist platform access tokens, refresh tokens, bot tokens,
authorization codes or platform runtime moderation data. A data-flow review is
required whenever a new adapter or provider is introduced.
