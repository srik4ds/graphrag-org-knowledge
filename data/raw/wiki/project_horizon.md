---
type: project
id: proj_horizon
name: Project Horizon
aliases: [Horizon, Payments API v3]
category: product
status: active
owner_team: Payments Team
start_date: 2026-02-01
end_date: null
uses: [Kubernetes, Kong, PostgreSQL]
members:
  - {person: Maria Garcia, role: Engineering Manager, start: 2026-02-01}
  - {person: dkim, role: Backend Engineer, start: 2026-02-01}
  - {person: Nina Sato, role: Product Manager, start: 2026-02-01}
  - {person: Alex Chen, role: Platform Advisor, start: 2026-08-01}
releases:
  - {id: rel_horizon_v3_ga, name: Horizon v3 GA, target_date: 2026-11-20, depends_on: [payments-api]}
author: Nina Sato
updated: 2026-09-25
---

# Project Horizon

## Goal

Project Horizon delivers version 3 of the public payments API. It adds idempotency keys on every write endpoint, webhooks with signed payloads, and a partner tier with higher rate limits behind the Kong API gateway.

## Scope

1. New endpoints for payment intents and refunds.
2. Signed webhooks with retry and replay protection.
3. Partner onboarding with OAuth2 client credentials (see ADR-008).
4. Migration guide for v2 customers, with v2 supported until June 2027.

## Team

Maria Garcia manages the team. David Kim is the main backend engineer and the owner of payments-api. Nina Sato is the product manager and owns the partner rollout. Alex Chen joined as a platform advisor in August 2026 because payments-api depends on ledger-db and auth-service.

## Dependencies

payments-api writes every transaction to ledger-db and validates tokens through auth-service. Any instability in those two services delays Horizon v3 GA.
