---
type: service
id: svc_kafka
name: kafka-cluster
aliases: [Kafka, kafka cluster, MSK]
owner_team: Data Engineering
owner: Ben Wright
depends_on: []
uses: [Terraform]
tier: 1
author: Ben Wright
updated: 2026-07-14
---

# kafka-cluster

## Summary

kafka-cluster is the Amazon MSK cluster that carries business events between services. It has three brokers across three availability zones and is provisioned with Terraform.

## Ownership

Data Engineering owns kafka-cluster. Ben Wright is the primary owner and Priya Patel is the escalation contact.

## Topics

1. payments.v1: payment lifecycle events from payments-api.
2. ledger.v1: ledger entries captured from ledger-db.
3. auth.audit.v1: authentication audit events.

Retention is 7 days for business topics and 30 days for audit topics.
