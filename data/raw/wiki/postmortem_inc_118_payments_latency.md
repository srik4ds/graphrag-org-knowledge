---
type: postmortem
id: doc_pm_inc_118
name: "Postmortem INC-118: payments-api latency spike"
incident: INC-118
about: [payments-api, Project Horizon]
author: David Kim
updated: 2026-08-06
---

# Postmortem INC-118: payments-api latency spike on 3 August 2026

## Impact

Between 09:10 and 09:55 UTC, p99 latency for create-payment rose from 250 ms to 4.2 seconds. No requests failed, but two large merchants hit client-side timeouts. Severity SEV2.

## Root cause

A Kong rate-limiting plugin was switched from local to cluster mode during a Horizon partner-tier test. Cluster mode stores counters in PostgreSQL, and each request added a round trip to an overloaded counter table.

## Resolution

David Kim reverted the plugin to local mode at 09:52. The partner-tier rate limits now use a Redis-backed counter, tested in staging under production load first.

## Action items

1. Load-test gateway plugin changes before enabling them in production (owner David Kim).
2. Add a latency SLO alert for the gateway separately from the service (owner Maria Garcia).
