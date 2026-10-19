---
type: project
id: proj_q2_sox_audit
name: Q2 2026 SOX Audit
aliases: [Q2 SOX audit, Q2 2026 audit]
category: audit
status: completed
owner_team: Security & Compliance
start_date: 2026-04-01
end_date: 2026-06-30
uses: [AuditBoard, Snowflake]
members:
  - {person: Raj Malhotra, role: Audit Lead, start: 2026-04-01, end: 2026-06-30}
  - {person: S. Jenkins, role: Evidence Automation Engineer, start: 2026-04-01, end: 2026-06-30}
  - {person: lnguyen, role: Data Controls Analyst, start: 2026-04-15, end: 2026-06-30}
author: Raj Malhotra
updated: 2026-07-02
---

# Q2 2026 SOX Audit

## Purpose

The Q2 2026 SOX audit re-tested the IT general controls for the ledger platform and validated the remediation of the Q4 2025 change management finding. The main goal for this cycle was to replace manual screenshots with automated, query-based evidence so that every control test can be re-run on demand.

## Evidence automation

Sarah Jenkins built the evidence automation. She wrote scheduled jobs that export deployment approvals and access grants into Snowflake, and parameterised queries that produce each evidence pack with a timestamp and a checksum. The external auditor accepted the query output directly, which cut evidence collection from about 300 hours in the previous cycle to under 90 hours.

## Data controls

Linh Nguyen joined in mid April to test the data controls around financial reporting tables. She validated row counts and reconciliation checks between the ledger and the reporting warehouse and documented each control in AuditBoard.

## Result

The audit closed on 30 June 2026 with no findings. The change management control now blocks any production deployment that lacks an approved change record. The sign-off memo is filed under "Q2 2026 SOX Audit sign-off".

## What happens next

After the audit, Sarah Jenkins moved to Project Triton and Linh Nguyen moved to Project Atlas. Raj Malhotra stays on the compliance roadmap and is planning the Q4 2026 cycle.
