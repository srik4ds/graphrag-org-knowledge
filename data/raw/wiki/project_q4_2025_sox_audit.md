---
type: project
id: proj_q4_2025_sox_audit
name: Q4 2025 SOX Audit
aliases: [Q4 2025 audit, FY25 SOX audit]
category: audit
status: completed
owner_team: Security & Compliance
start_date: 2025-10-01
end_date: 2025-12-15
uses: [AuditBoard, ServiceNow]
members:
  - {person: Raj Malhotra, role: Audit Lead, start: 2025-10-01, end: 2025-12-15}
  - {person: J. Owusu, role: Access Review Owner, start: 2025-10-01, end: 2025-12-15}
  - {person: tbrooks, role: Change Management Evidence, start: 2025-10-15, end: 2025-12-10}
author: Raj Malhotra
updated: 2025-12-18
---

# Q4 2025 SOX Audit

## Scope

The Q4 2025 SOX audit covered the IT general controls (ITGCs) that support Fintara's financial reporting: logical access to the ledger platform, change management for production deployments, and backup and recovery for ledger-db. The external auditor sampled 25 production changes and 40 access grants from the period July to September 2025.

## Team

Raj Malhotra led the audit and owned the relationship with the external auditor. James Owusu ran the quarterly access reviews for every system in scope and produced the user access listings. Tom Brooks from the Platform Team pulled change management evidence from ServiceNow and the deployment pipeline logs.

## Outcome

The audit closed on 15 December 2025 with one moderate finding: four production changes to ledger-db were deployed without a linked, approved change ticket. The remediation plan committed the Platform Team to block deployments that lack an approved ServiceNow change record. Evidence collection took roughly 300 hours, most of it manual screenshots and spreadsheet reconciliation, which led to the evidence automation work in the next audit cycle.

## Lessons learned

1. Evidence requests arrive in bursts; a shared evidence calendar reduced last-minute escalations.
2. Manual screenshots are fragile. Query-based evidence from the warehouse is easier to re-run and to explain.
3. Access reviews should be scheduled monthly instead of quarterly for privileged roles.
