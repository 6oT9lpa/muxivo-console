# Muxivo Console Retention Policy — Draft

This is an operational baseline for review by the data owner and counsel. A
legal hold pauses deletion only for the specifically covered records.

| Record | Baseline retention | Deletion/anonymization trigger | Owner |
| --- | --- | --- | --- |
| Active account | While active | Verified account deletion request | `TBD` |
| Password credentials | While identity is usable | Identity removal or account deletion | `TBD` |
| Expired/revoked sessions | 30 days after expiry/revocation | Scheduled security cleanup | Engineering |
| Password recovery transactions | 24 hours after expiry/consumption | Scheduled security cleanup | Engineering |
| Organization metadata | While organization exists | Approved organization deletion | Organization owner + `TBD` |
| Active memberships | While membership is active | Member removal or account deletion | Organization owner |
| Membership audit facts | 1 year minimum | Approved retention expiry | Security owner `TBD` |
| Platform connection metadata | While connection exists | Disconnect/revoke/delete request | Organization owner |
| Connection audit facts | 1 year minimum | Approved retention expiry | Security owner `TBD` |
| Application logs | 30–90 days | Provider retention expiry | Operations owner `TBD` |
| Aggregated metrics | 90 days | Monitoring retention expiry | Operations owner `TBD` |
| Backups | 30 days for daily backups | Backup expiry after restore checks | Operations owner `TBD` |

## Enforcement

- The scheduled cleanup worker removes only expired session and recovery records
  after their cutoffs.
- Audit facts remain secret-free and are retained separately from removable
  credentials.
- Backups must use the selected encrypted storage and access controls.
- Deletion requests require identity verification and recent authentication for
  sensitive actions; the procedure must record the decision and outcome.
- Legal holds, incident preservation and statutory requirements must be tracked
  by a named owner before a deletion job is paused.

## Review cadence

Review this policy before staging, after any new data integration and at least
annually after launch. The final approver and review date are `TBD`.
