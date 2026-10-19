---
type: runbook
id: doc_rb_payments_api
name: payments-api on-call runbook
about: [payments-api]
author: Maria Garcia
updated: 2026-09-02
---

# payments-api on-call runbook

## Severity levels

1. SEV1: payments failing for more than 1% of requests, or any data integrity risk to the ledger.
2. SEV2: latency SLO breached for more than 15 minutes, no failed payments.
3. SEV3: degraded non-critical endpoint, such as reporting exports.

## Escalation for a SEV1

1. The primary on-call engineer from the Payments Team acknowledges the page within 5 minutes and opens an incident channel named inc-<number>.
2. Within 10 minutes, page the secondary on-call and the escalation manager, Maria Garcia.
3. If ledger-db or auth-service is involved, page the Platform Team on-call immediately; do not wait for the 10-minute mark.
4. The escalation manager informs the VP Engineering, Elena Fischer, for any SEV1 lasting longer than 30 minutes.
5. Customer support posts a status page update within 15 minutes of declaring a SEV1.

## First checks

1. Kong gateway error rate and plugin changes in the last hour.
2. auth-service token validation latency.
3. ledger-db connection pool usage in PgBouncer.

## After the incident

The incident commander files a Jira incident ticket and schedules a blameless postmortem within 5 business days.
