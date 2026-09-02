# Muxivo Console Incident Runbook — Draft

This runbook is a starting point for staging rehearsal. Replace owners,
contacts, monitoring URLs and escalation paths before production approval.

## Roles and contacts

- Incident commander: `TBD`
- Technical lead: `TBD`
- Security owner: `TBD`
- Communications/legal contact: `TBD`
- Monitoring/alert destination: `TBD`

## Severity

| Severity | Example | Target initial response |
| --- | --- | --- |
| SEV-1 | Confirmed credential/token exposure, active compromise or data exfiltration | Immediate page |
| SEV-2 | Authentication bypass, privilege escalation or widespread outage | Within 15 minutes |
| SEV-3 | Limited security defect or degraded adapter lifecycle | Same business day |

## First hour

1. Assign the incident commander and scribe.
2. Record the start time, affected deployment SHA and an immutable timeline.
3. Preserve relevant redacted logs, metrics and audit events without copying
   secrets or raw session/recovery tokens.
4. Identify the blast radius across users, organizations, memberships,
   connections and data classes.
5. Stop ongoing exposure: disable risky routes, revoke sessions, rotate
   affected secrets or disconnect affected platform connections.
6. Keep public and internal updates factual; do not speculate about users or
   providers.
7. Engage legal/privacy contacts when personal data or notification duties may
   be involved.

## Recovery

1. Confirm the root cause and add a regression test or detection rule.
2. Rotate only the affected credentials, using the approved secret manager.
3. Rebuild and deploy through the staged rollout with a recorded SHA.
4. Verify health, metrics, authentication, organization access, audit and
   connection lifecycle behavior.
5. Re-enable paused operations gradually and monitor the alert window.
6. Complete a post-incident review with owners and due dates.

## Evidence and communication rules

- Never place passwords, provider tokens, recovery tokens or authorization codes
  in tickets, chat, screenshots or incident documents.
- Use correlation IDs, deployment SHAs and event IDs to link evidence.
- Preserve only the minimum records required for investigation and legal hold.
- The notification decision, recipient list and timing are owned by `TBD`.
