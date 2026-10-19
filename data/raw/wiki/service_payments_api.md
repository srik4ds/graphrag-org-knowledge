---
type: service
id: svc_payments_api
name: payments-api
aliases: [payments API, payment service]
owner_team: Payments Team
owner: David Kim
depends_on: [ledger-db, auth-service]
uses: [Kong, Kubernetes]
tier: 0
author: David Kim
updated: 2026-09-20
---

# payments-api

## Summary

payments-api is the public REST API that merchants and partners call to create payments, refunds and payouts. It runs on Kubernetes behind the Kong gateway, which handles rate limiting and authentication plugins.

## Ownership

The Payments Team owns payments-api. David Kim is the primary owner. Maria Garcia is the escalation manager.

## Dependencies

1. ledger-db: every write endpoint commits a ledger entry before returning.
2. auth-service: validates OAuth2 tokens and API keys on every request.

If either dependency is degraded, payments-api returns HTTP 503 with a Retry-After header instead of queueing writes.

## Service levels

1. Availability target 99.95% per calendar month.
2. p99 latency target 300 ms for create-payment.
