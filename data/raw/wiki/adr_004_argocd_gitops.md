---
type: decision
id: adr_004
name: "ADR-004: Adopt ArgoCD for GitOps deployments"
aliases: [ADR-004, ArgoCD decision, GitOps decision]
status: accepted
date: 2026-03-18
decided_by: Platform Team
proposed_by: tbrooks
approved_by: [Elena Fischer]
affects: [Project Triton]
tags: [deployment, gitops]
author: Tom Brooks
updated: 2026-03-18
---

# ADR-004: Adopt ArgoCD for GitOps deployments

## Context

Deployments to the legacy hosts are driven by shell scripts in CI. There is no single place that shows what version of each service runs in each environment, and rollbacks are manual.

## Decision

All services on the Triton clusters are deployed by ArgoCD from the platform-apps repository. CI builds and pushes images; a pull request that bumps the image tag is the only way to deploy.

## Alternatives considered

1. Flux: similar model, but the team already had ArgoCD experience.
2. Keep CI push deployments: rejected because it does not give drift detection.

## Consequences

Every production change now has a reviewed pull request, which also satisfies the SOX change management control. Proposed by Tom Brooks and approved by Elena Fischer on 18 March 2026.
