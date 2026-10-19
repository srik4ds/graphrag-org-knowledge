---
type: project
id: proj_triton
name: Project Triton
aliases: [Triton, Triton migration]
category: infrastructure
status: active
owner_team: Platform Team
start_date: 2026-03-01
end_date: null
uses: [Terraform, Kubernetes, ArgoCD]
members:
  - {person: A. Chen, role: Tech Lead, start: 2026-03-01}
  - {person: tbrooks, role: SRE, start: 2026-03-15}
  - {person: Sarah Jenkins, role: Cloud Engineer, start: 2026-07-06}
releases:
  - {id: rel_triton_ga, name: Triton GA, target_date: 2026-12-10, depends_on: [ledger-db, auth-service]}
author: Alex Chen
updated: 2026-09-30
---

# Project Triton

## Goal

Project Triton moves the ledger platform from hand-managed EC2 hosts to Amazon EKS, with all infrastructure defined in Terraform and all deployments driven by ArgoCD. The target is a reproducible platform where any environment can be rebuilt from code in under two hours.

## Architecture draft

The platform runs on three EKS clusters (dev, staging, prod) in separate AWS accounts. Terraform modules define the VPCs, the EKS clusters, IAM roles for service accounts and the Aurora PostgreSQL cluster that will replace the current ledger-db hosts. ArgoCD watches the platform-apps repository and syncs each service into its namespace.

The infrastructure stack chosen for the Triton deployment is managed through Terraform modules authored by S. Jenkins after she joined the project in July 2026. Before July the modules were prototypes written by Alex Chen. Tom Brooks owns the cluster add-ons, observability with Datadog, and the on-call runbooks for the new platform.

## Milestones

1. March 2026: project kickoff, landing zone design.
2. July 2026: production-grade Terraform modules and EKS baseline.
3. October 2026: ledger-db migration rehearsal to Aurora PostgreSQL.
4. December 2026: Triton GA, with ledger-db and auth-service running on the new platform.

## Risks

1. The ledger-db migration needs a zero-downtime cutover. The October rehearsal caused the INC-142 outage and must be repeated.
2. ArgoCD sync failures on auth-service are still open.
3. Knowledge of ledger-db internals is concentrated in Alex Chen, which is a key-person risk for Triton GA.
