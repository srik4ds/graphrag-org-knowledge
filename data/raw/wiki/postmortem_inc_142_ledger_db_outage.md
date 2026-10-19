---
type: postmortem
id: doc_pm_inc_142
name: "Postmortem INC-142: ledger-db outage"
incident: INC-142
about: [ledger-db, Project Triton]
author: T. Brooks
updated: 2026-10-15
---

# Postmortem INC-142: ledger-db outage on 12 October 2026

## Impact

From 14:05 to 14:52 UTC on 12 October 2026, ledger-db refused new connections. payments-api returned HTTP 503 for 47 minutes and about 18,000 payment attempts failed. Severity SEV1.

## Timeline

1. 13:40 Migration rehearsal for TRI-12 starts against the production primary, with a schema change that adds a column with a default to the entries table.
2. 14:02 The ALTER TABLE waits on a long-running reporting query and takes an ACCESS EXCLUSIVE lock as soon as it is granted.
3. 14:05 Every new transaction queues behind the lock. PgBouncer's 400 server connections fill up within 90 seconds and new clients are refused.
4. 14:21 Tom Brooks pages Alex Chen, the ledger-db owner.
5. 14:44 Alex Chen cancels the migration session; the lock is released.
6. 14:52 Connection pool drains and error rates return to normal.

## Root cause

The rehearsal ran a blocking DDL statement against the production primary without lock_timeout. The statement queued behind a reporting query, then held an exclusive lock that blocked all writes, which exhausted the PgBouncer connection pool. Detection was slow because the alert on pool saturation was routed to a muted channel.

## Contributing factors

1. The rehearsal runbook pointed at the production host name instead of the rehearsal replica.
2. Only Alex Chen knew how to safely kill the session without corrupting the migration state.

## Action items

1. Enforce lock_timeout = 5s on all migration roles (owner Alex Chen).
2. Route PgBouncer saturation alerts to the Platform on-call pager (owner Tom Brooks).
3. Run future rehearsals only on a restored snapshot (owner Sarah Jenkins).
4. Write a ledger-db emergency runbook so more than one engineer can act (owner Alex Chen).
