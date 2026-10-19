---
type: decision
id: adr_008
name: "ADR-008: OAuth2 client credentials for the partner API"
aliases: [ADR-008, partner OAuth decision]
status: accepted
date: 2026-06-10
decided_by: Payments Team
proposed_by: Nina Sato
approved_by: [Maria Garcia, James Owusu]
affects: [Project Horizon]
tags: [api-security, partners]
author: Nina Sato
updated: 2026-06-10
---

# ADR-008: OAuth2 client credentials for the partner API

## Context

Partners on the new Horizon partner tier call payments-api from their servers. Long-lived API keys are hard to scope and to revoke.

## Decision

Partners authenticate with the OAuth2 client credentials grant. Access tokens live for 15 minutes and carry scopes per endpoint group. Client secrets are issued through the partner portal and stored hashed.

## Consequences

The Payments Team owns the partner onboarding flow. auth-service must support the client credentials grant before Horizon v3 GA.

Proposed by Nina Sato. Approved by Maria Garcia and James Owusu on 10 June 2026.
