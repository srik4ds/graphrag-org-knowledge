---
type: service
id: svc_ledger_db
name: ledger-db
aliases: [ledger database, ledger DB]
owner_team: Platform Team
owner: A. Chen
depends_on: []
uses: [PostgreSQL]
tier: 0
author: Alex Chen
updated: 2026-09-12
---

# ledger-db

## Summary

ledger-db is the system of record for every money movement at Fintara. It is a PostgreSQL 14 cluster with one primary and two synchronous replicas, fronted by PgBouncer for connection pooling. It is a tier 0 service: any outage stops payments.

## Ownership

The Platform Team owns ledger-db. Alex Chen is the primary owner and the only engineer who has run a major version upgrade on it. On-call is shared by the Platform Team rotation.

## Consumers

1. payments-api writes every transaction and reads balances.
2. auth-service stores API client records in a separate schema.
3. A change data capture connector copies ledger entries to kafka-cluster (topic ledger.v1). This is a soft dependency: if ledger-db is down, analytics is delayed but event-stream keeps running.

## Operational notes

1. PgBouncer runs in transaction pooling mode with a pool of 400 server connections.
2. Long-running DDL takes an ACCESS EXCLUSIVE lock; always run schema changes with lock_timeout set.
3. The migration to Aurora PostgreSQL is tracked under Project Triton (TRI-12).
