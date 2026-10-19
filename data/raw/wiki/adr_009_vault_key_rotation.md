---
type: decision
id: adr_009
name: "ADR-009: Rotate API key secrets in Vault every 30 days"
aliases: [ADR-009, key rotation decision, Vault rotation]
status: accepted
date: 2026-08-14
decided_by: Platform Team
proposed_by: S. Jenkins
approved_by: [Elena Fischer]
affects: [Project Triton]
tags: [api-security, secrets]
author: Sarah Jenkins
updated: 2026-08-14
---

# ADR-009: Rotate API key secrets in Vault every 30 days

## Context

Legacy v2 API keys never expire. The Q2 2026 audit noted that key age is not monitored, although it was not raised as a finding.

## Decision

API key secrets for v2 customers are stored in HashiCorp Vault and rotate automatically every 30 days, with a 7-day overlap window so customers can switch without downtime. auth-service reads the current and previous secret from Vault.

## Consequences

Customer success must notify v2 customers before the first rotation. Platform Team owns the rotation job; Security & Compliance monitors key age monthly.

Proposed by Sarah Jenkins. Approved by Elena Fischer on 14 August 2026.
