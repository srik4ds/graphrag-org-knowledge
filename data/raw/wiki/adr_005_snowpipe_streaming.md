---
type: decision
id: adr_005
name: "ADR-005: Snowpipe Streaming for event ingestion"
aliases: [ADR-005, Snowpipe Streaming decision, Kafka Connect decision]
status: accepted
date: 2026-04-22
decided_by: Data Engineering
proposed_by: P. Patel
approved_by: [Elena Fischer]
affects: [Project Atlas, Project Horizon]
tags: [ingestion, streaming, data-platform]
author: Priya Patel
updated: 2026-04-22
---

# ADR-005: Snowpipe Streaming for event ingestion

## Context

Project Atlas needs payment and ledger events in Snowflake within seconds. The two realistic options were the Snowflake Kafka Connector running on a Kafka Connect cluster, or lightweight consumers in the event-stream service that call the Snowpipe Streaming API directly.

## Decision

We use Snowpipe Streaming from our own consumers. We do not run a Kafka Connect cluster.

## Rationale

1. Latency: in the April benchmark, Snowpipe Streaming delivered rows with a p95 of 6 seconds, compared with 45 to 70 seconds for the file-based connector configuration we tested.
2. Fewer moving parts: Kafka Connect would add a cluster to run, patch and monitor, and nobody on the Data Engineering team has operated one in production.
3. Cost: there are no staging files and no separate warehouse for loading, so ingestion cost scales with rows instead of files.
4. Exactly-once: offset tokens let each consumer resume without duplicates after a restart.

## Consequences

Data Engineering owns the consumer code in event-stream. Payments events published by Project Horizon must follow the event registry schema rules so the consumers can load them.

Proposed by Priya Patel. Approved by Elena Fischer on 22 April 2026.
