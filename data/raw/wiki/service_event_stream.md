---
type: service
id: svc_event_stream
name: event-stream
aliases: [event stream, events pipeline]
owner_team: Data Engineering
owner: Ben Wright
depends_on: [kafka-cluster]
uses: [Snowpipe Streaming]
tier: 1
author: Ben Wright
updated: 2026-09-18
---

# event-stream

## Summary

event-stream publishes payment and ledger events for analytics. Producers write to topics on kafka-cluster, and a set of consumers loads the events into Snowflake with Snowpipe Streaming.

## Ownership

Data Engineering owns event-stream. Ben Wright is the primary owner.

## Design notes

1. Each consumer commits Snowpipe Streaming offset tokens only after Snowflake acknowledges the rows, which gives exactly-once loading per channel.
2. Schema changes are versioned in the event registry; consumers reject unknown major versions.
3. End-to-end latency target is under 10 seconds at p95.
