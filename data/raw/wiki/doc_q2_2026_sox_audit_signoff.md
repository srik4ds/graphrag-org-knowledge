---
type: document
id: doc_q2_sox_signoff
name: Q2 2026 SOX Audit sign-off
about: [Q2 2026 SOX Audit]
author: R. Malhotra
updated: 2026-07-02
---

# Q2 2026 SOX Audit sign-off memo

**To:** Elena Fischer, VP Engineering
**From:** Raj Malhotra, Compliance Lead
**Date:** 2 July 2026

The Q2 2026 SOX audit of the ledger platform IT general controls is complete. The external auditor issued a clean opinion with no exceptions.

## Controls tested

1. Logical access to ledger-db and auth-service (privileged and standard roles).
2. Change management for production deployments, including the new approval gate.
3. Backup and restore testing for ledger-db.
4. Reconciliation controls between the ledger and the reporting warehouse.

## Contributors

The audit team was R. Malhotra (lead), S. Jenkins (evidence automation) and L. Nguyen (data controls). Their automated evidence packs are stored in the audit evidence schema in Snowflake and can be regenerated for any period.

## Remediation status

The Q4 2025 finding on unapproved changes to ledger-db is closed. Deployments without an approved change ticket are now rejected automatically by the pipeline.

Signed, Raj Malhotra
