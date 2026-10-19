---
type: decision
id: adr_007
name: "ADR-007: Mutual TLS for internal service-to-service APIs"
aliases: [ADR-007, mTLS decision]
status: accepted
date: 2026-05-20
decided_by: Platform Team
proposed_by: Alex Chen
approved_by: [Elena Fischer, James Owusu]
affects: [Project Triton, Project Horizon]
tags: [api-security, networking]
author: Alex Chen
updated: 2026-05-20
---

# ADR-007: Mutual TLS for internal service-to-service APIs

## Context

Internal API calls between payments-api, auth-service and ledger-db consumers rely on network policy only. A compromised pod inside the cluster could call any internal endpoint.

## Decision

Every internal service-to-service API call uses mutual TLS. Certificates are issued per service by the cluster certificate authority and rotate every 24 hours. Calls without a valid client certificate are rejected at the sidecar.

## Alternatives considered

1. Shared bearer tokens between services: rejected because tokens leak into logs and are hard to rotate.
2. Network policy only: kept as a second layer, but not sufficient on its own.

## Approval

Proposed by Alex Chen. Approved by Elena Fischer and reviewed by James Owusu from Security & Compliance on 20 May 2026.
