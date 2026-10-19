---
type: project
id: proj_atlas
name: Project Atlas
aliases: [Atlas, Atlas data platform]
category: data-platform
status: active
owner_team: Data Engineering
start_date: 2026-05-01
end_date: null
uses: [Snowflake, dbt, Airflow, Snowpipe Streaming]
members:
  - {person: Priya Patel, role: Tech Lead, start: 2026-05-01}
  - {person: Ben Wright, role: Data Engineer, start: 2026-05-01}
  - {person: L. Nguyen, role: Analytics Engineer, start: 2026-07-01}
releases:
  - {id: rel_atlas_beta, name: Atlas Beta, target_date: 2026-11-05, depends_on: [event-stream]}
author: Priya Patel
updated: 2026-09-28
---

# Project Atlas

## Goal

Project Atlas builds Fintara's near real-time data platform. Payment and ledger events land in Snowflake within seconds, dbt models turn them into finance-ready marts, and Airflow orchestrates the batch reconciliation jobs that still run nightly.

## Design

Events are published to the event-stream service and ingested with Snowpipe Streaming, following ADR-005. Raw tables are append-only. dbt builds three layers: staging, intermediate and marts. The finance marts feed the regulatory reports and the month-end close dashboards.

Linh Nguyen joined the project in July 2026 after the Q2 audit. She owns the dbt marts and the data quality tests, reusing the reconciliation checks she wrote for the audit. Ben Wright owns ingestion and the event-stream consumers. Priya Patel leads the project and owns the architecture.

## Milestones

1. May 2026: kickoff and ADR-005 accepted.
2. August 2026: first streaming pipeline in staging.
3. November 2026: Atlas Beta for the finance team.

## Open questions

1. How long to keep raw events in Snowflake before archiving to S3.
2. Whether the nightly reconciliation can move to a streaming check.
