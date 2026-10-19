# GraphRAG vs Vector RAG: evaluation report

## Summary

| # | Metric | GraphRAG | Vector-only |
|---|---|---|---|
| 1 | Correctness (avg, 0-1) | 0.8 | 0.35 |
| 2 | Relevance (avg, 0-1) | 0.95 | 0.8 |
| 3 | Faithfulness (avg of answered) | 1.0 | 1.0 |
| 4 | Fact recall (avg) | 0.815 | 0.393 |
| 5 | Refusals | 0 | 0 |
| 6 | Latency p50 (ms) | 514.1 | 330.1 |
| 7 | Latency p95 (ms) | 1148.7 | 355.0 |

## Per-question comparison

| # | Id | Question | Expected | GraphRAG correctness | Vector correctness | Winner |
|---|---|---|---|---|---|---|
| 1 | Q01 | Who worked on the last compliance audit, and what tools are used on the project each of them moved to next? | graph | 1.0 | 0.5 | GraphRAG |
| 2 | Q02 | What API security decisions were made by the team that owns the service that failed in the most recent incident? | graph | 1.0 | 0.5 | GraphRAG |
| 3 | Q03 | If Alex Chen leaves the company next month, which product releases are at risk? | graph | 0.5 | 0.0 | GraphRAG |
| 4 | Q04 | Who approved the decision to use Snowpipe Streaming instead of Kafka Connect, and which projects does that decision affect? | tie | 1.0 | 0.5 | GraphRAG |
| 5 | Q05 | Which open tickets are blocking the Triton GA release, and who is each one assigned to? | graph | 1.0 | 0.0 | GraphRAG |
| 6 | Q06 | Which tools has Linh Nguyen used across all of her projects? | graph | 1.0 | 0.5 | GraphRAG |
| 7 | Q07 | Why did the data team choose Snowpipe Streaming over Kafka Connect? | vector | 1.0 | 1.0 | Tie |
| 8 | Q08 | What was the root cause of the ledger-db outage in October 2026? | vector | 0.0 | 0.0 | Tie |
| 9 | Q09 | What is the escalation process for a SEV1 on payments-api? | vector | 0.5 | 0.5 | Tie |
| 10 | Q10 | Who has the most open tickets on Project Atlas, and what are they? | graph | 1.0 | 0.0 | GraphRAG |

## Answers

### Q01: Who worked on the last compliance audit, and what tools are used on the project each of them moved to next?

**Gold:** The last compliance audit was the Q2 2026 SOX Audit (ended 2026-06-30), staffed by Raj Malhotra, Sarah Jenkins and Linh Nguyen. Sarah Jenkins moved to Project Triton, which uses Terraform, Kubernetes and ArgoCD. Linh Nguyen moved to Project Atlas, which uses Snowflake, dbt, Airflow and Snowpipe Streaming. Raj Malhotra has no later project recorded.

**graphrag** (answered, 1148.7 ms, correctness 1.0, recall 1.0, strategy template:project_people_next_projects):

1. Linh Nguyen worked on Q2 2026 SOX Audit (2026-04-01 to 2026-06-30) as Data Controls Analyst. Next project: Project Atlas (from 2026-07-01), which uses Snowflake, dbt, Airflow, Snowpipe Streaming. [G1]
2. Raj Malhotra worked on Q2 2026 SOX Audit (2026-04-01 to 2026-06-30) as Audit Lead. No later project is recorded. [G2]
3. Sarah Jenkins worked on Q2 2026 SOX Audit (2026-04-01 to 2026-06-30) as Evidence Automation Engineer. Next project: Project Triton (from 2026-07-06), which uses Kubernetes, Terraform, ArgoCD. [G3]
4. After the audit, Sarah Jenkins moved to Project Triton and Linh Nguyen moved to Project Atlas. [V1]
5. The Q2 2026 SOX audit re-tested the IT general controls for the ledger platform and validated the remediation of the Q4 2025 change management finding. [V1]
6. The audit closed on 30 June 2026 with no findings. [V1]
7. Linh Nguyen joined the project in July 2026 after the Q2 audit. [V2]
8. Project Atlas builds Fintara's near real-time data platform. [V2]
9. Payment and ledger events land in Snowflake within seconds, dbt models turn them into finance-ready marts, and Airflow orchestrates the batch reconciliation jobs that still run nightly. [V2]
10. Evidence collection took roughly 300 hours, most of it manual screenshots and spreadsheet reconciliation, which led to the evidence automation work in the next audit cycle. [V3]
11. The Q4 2025 SOX audit covered the IT general controls (ITGCs) that support Fintara's financial reporting: logical access to the ledger platform, change management for production deployments, and backup and recovery for ledger-db. [V3]
12. Raj Malhotra led the audit and owned the relationship with the external auditor. [V3]

_Judge: offline word overlap 0.87_

**vector** (answered, 352.8 ms, correctness 0.5, recall 0.667, strategy -):

1. After the audit, Sarah Jenkins moved to Project Triton and Linh Nguyen moved to Project Atlas. [V1]
2. The Q2 2026 SOX audit re-tested the IT general controls for the ledger platform and validated the remediation of the Q4 2025 change management finding. [V1]
3. The audit closed on 30 June 2026 with no findings. [V1]
4. Linh Nguyen joined the project in July 2026 after the Q2 audit. [V2]
5. Project Atlas builds Fintara's near real-time data platform. [V2]
6. Payment and ledger events land in Snowflake within seconds, dbt models turn them into finance-ready marts, and Airflow orchestrates the batch reconciliation jobs that still run nightly. [V2]
7. Evidence collection took roughly 300 hours, most of it manual screenshots and spreadsheet reconciliation, which led to the evidence automation work in the next audit cycle. [V3]
8. The Q4 2025 SOX audit covered the IT general controls (ITGCs) that support Fintara's financial reporting: logical access to the ledger platform, change management for production deployments, and backup and recovery for ledger-db. [V3]
9. Raj Malhotra led the audit and owned the relationship with the external auditor. [V3]
10. auth.audit.v1: authentication audit events. [V4]
11. Retention is 7 days for business topics and 30 days for audit topics. [V4]

_Judge: offline word overlap 0.58_

### Q02: What API security decisions were made by the team that owns the service that failed in the most recent incident?

**Gold:** The most recent incident is INC-142 (2026-10-12), a ledger-db outage. ledger-db is owned by the Platform Team. The Platform Team's API security decisions are ADR-007 (mutual TLS for internal service-to-service APIs, approved by Elena Fischer and James Owusu) and ADR-009 (rotate API key secrets in Vault every 30 days, approved by Elena Fischer). ADR-008 is an API security decision but belongs to the Payments Team.

**graphrag** (answered, 539.6 ms, correctness 1.0, recall 0.5, strategy template:incident_owner_decisions):

1. Incident INC-142 (SEV1, 2026-10-12: ledger-db outage: connection pool exhausted) affected the service ledger-db, which is owned by Platform Team. [G1]
2. Platform Team decision ADR-004: Adopt ArgoCD for GitOps deployments (date 2026-03-18, tags: deployment, gitops; approved by Elena Fischer). [G2]
3. Platform Team decision ADR-007: Mutual TLS for internal service-to-service APIs (date 2026-05-20, tags: api-security, networking; approved by James Owusu, Elena Fischer). [G3]
4. Platform Team decision ADR-009: Rotate API key secrets in Vault every 30 days (date 2026-08-14, tags: api-security, secrets; approved by Elena Fischer). [G4]
5. The primary on-call engineer from the Payments Team acknowledges the page within 5 minutes and opens an incident channel named inc-<number>. [V1]
6. SEV2: latency SLO breached for more than 15 minutes, no failed payments. [V1]
7. If ledger-db or auth-service is involved, page the Platform Team on-call immediately; do not wait for the 10-minute mark. [V1]
8. The Platform Team owns ledger-db. [V2]
9. It is a tier 0 service: any outage stops payments. [V2]
10. On-call is shared by the Platform Team rotation. [V2]
11. The Payments Team owns the partner onboarding flow. [V3]
12. ADR-008: OAuth2 client credentials for the partner API. [V3]
13. Long-lived API keys are hard to scope and to revoke. [V3]

_Judge: offline word overlap 0.84_

**vector** (answered, 325.6 ms, correctness 0.5, recall 0.2, strategy -):

1. The primary on-call engineer from the Payments Team acknowledges the page within 5 minutes and opens an incident channel named inc-<number>. [V1]
2. SEV2: latency SLO breached for more than 15 minutes, no failed payments. [V1]
3. If ledger-db or auth-service is involved, page the Platform Team on-call immediately; do not wait for the 10-minute mark. [V1]
4. The Platform Team owns ledger-db. [V2]
5. It is a tier 0 service: any outage stops payments. [V2]
6. On-call is shared by the Platform Team rotation. [V2]
7. The Payments Team owns the partner onboarding flow. [V3]
8. ADR-008: OAuth2 client credentials for the partner API. [V3]
9. Long-lived API keys are hard to scope and to revoke. [V3]
10. Internal API calls between payments-api, auth-service and ledger-db consumers rely on network policy only. [V4]
11. Every internal service-to-service API call uses mutual TLS. [V4]
12. Certificates are issued per service by the cluster certificate authority and rotate every 24 hours. [V4]

_Judge: offline word overlap 0.38_

### Q03: If Alex Chen leaves the company next month, which product releases are at risk?

**Gold:** Alex Chen owns ledger-db and auth-service. Triton GA depends directly on both. Horizon v3 GA depends on payments-api, which depends on ledger-db and auth-service. Alex is also assigned open tickets that block these releases: TRI-12 (ledger-db migration, blocks Triton GA) and HOR-8 (client credentials in auth-service, blocks Horizon v3 GA). Atlas Beta is not affected.

**graphrag** (answered, 518.0 ms, correctness 0.5, recall 1.0, strategy template:person_departure_impact):

1. Alex Chen is the primary owner of: auth-service, ledger-db. [G1]
2. Release Triton GA (target 2026-12-10) depends on auth-service through the chain Triton GA -> auth-service. [G2]
3. Release Horizon v3 GA (target 2026-11-20) depends on auth-service through the chain Horizon v3 GA -> payments-api -> auth-service. [G3]
4. Release Triton GA (target 2026-12-10) depends on ledger-db through the chain Triton GA -> ledger-db. [G4]
5. Release Triton GA (target 2026-12-10) depends on ledger-db through the chain Triton GA -> auth-service -> ledger-db. [G5]
6. Release Horizon v3 GA (target 2026-11-20) depends on ledger-db through the chain Horizon v3 GA -> payments-api -> auth-service -> ledger-db. [G6]
7. Release Horizon v3 GA (target 2026-11-20) depends on ledger-db through the chain Horizon v3 GA -> payments-api -> ledger-db. [G7]
8. Alex Chen is assigned open ticket HOR-8 (Support OAuth2 client credentials grant in auth-service, status Open), which blocks release Horizon v3 GA. [G8]
9. Alex Chen what is your ETA?. [V1]
10. Alex Chen: I am heads-down on the ledger-db migration for Triton. [V1]
11. Maria Garcia: That puts Horizon v3 GA on 20 November at risk. [V1]
12. Alex Chen: Cancelled the migration session. [V2]

_Judge: offline word overlap 0.57_

**vector** (answered, 327.0 ms, correctness 0.0, recall 0.75, strategy -):

1. Alex Chen what is your ETA?. [V1]
2. Alex Chen: I am heads-down on the ledger-db migration for Triton. [V1]
3. Maria Garcia: That puts Horizon v3 GA on 20 November at risk. [V1]
4. Alex Chen: Cancelled the migration session. [V2]
5. 14:21 Tom Brooks pages Alex Chen, the ledger-db owner. [V3]
6. 14:44 Alex Chen cancels the migration session; the lock is released. [V3]
7. Only Alex Chen knew how to safely kill the session without corrupting the migration state. [V3]
8. Knowledge of ledger-db internals is concentrated in Alex Chen, which is a key-person risk for Triton GA. [V4]
9. Before July the modules were prototypes written by Alex Chen. [V4]
10. Alex Chen: On INC-142: the rehearsal runbook pointed at the prod primary host name. [V5]
11. Sarah Jenkins: Alex Chen I will build a snapshot-restore environment so rehearsals never touch prod again (TRI-23). [V5]
12. Elena Fischer: Alex, please pair with Sarah on the ledger-db emergency runbook. [V5]

_Judge: offline word overlap 0.27_

### Q04: Who approved the decision to use Snowpipe Streaming instead of Kafka Connect, and which projects does that decision affect?

**Gold:** ADR-005 was approved by Elena Fischer on 2026-04-22 (proposed by Priya Patel, decided by Data Engineering). It affects Project Atlas and Project Horizon.

**graphrag** (answered, 863.9 ms, correctness 1.0, recall 1.0, strategy template:decision_details):

1. ADR-005: Snowpipe Streaming for event ingestion (status accepted, dated 2026-04-22) was decided by Data Engineering, proposed by Priya Patel, approved by Elena Fischer, and affects Project Atlas, Project Horizon. [G1]
2. The two realistic options were the Snowflake Kafka Connector running on a Kafka Connect cluster, or lightweight consumers in the event-stream service that call the Snowpipe Streaming API directly. [V1]
3. We use Snowpipe Streaming from our own consumers. [V1]
4. ADR-005: Snowpipe Streaming for event ingestion. [V1]
5. Producers write to topics on kafka-cluster, and a set of consumers loads the events into Snowflake with Snowpipe Streaming. [V2]
6. Each consumer commits Snowpipe Streaming offset tokens only after Snowflake acknowledges the rows, which gives exactly-once loading per channel. [V2]
7. Approved by Maria Garcia and James Owusu on 10 June 2026. [V3]
8. Priya Patel: Benchmark results are in: Snowpipe Streaming p95 is 6 seconds; the Kafka connector in file mode was 45 to 70 seconds. [V4]
9. Also, nobody on the team wants to operate a Kafka Connect cluster. [V4]
10. Approved by Elena Fischer and reviewed by James Owusu from Security & Compliance on 20 May 2026. [V5]

_Judge: offline word overlap 1.00_

**vector** (answered, 323.4 ms, correctness 0.5, recall 0.333, strategy -):

1. The two realistic options were the Snowflake Kafka Connector running on a Kafka Connect cluster, or lightweight consumers in the event-stream service that call the Snowpipe Streaming API directly. [V1]
2. We use Snowpipe Streaming from our own consumers. [V1]
3. ADR-005: Snowpipe Streaming for event ingestion. [V1]
4. Producers write to topics on kafka-cluster, and a set of consumers loads the events into Snowflake with Snowpipe Streaming. [V2]
5. Each consumer commits Snowpipe Streaming offset tokens only after Snowflake acknowledges the rows, which gives exactly-once loading per channel. [V2]
6. Approved by Maria Garcia and James Owusu on 10 June 2026. [V3]
7. Priya Patel: Benchmark results are in: Snowpipe Streaming p95 is 6 seconds; the Kafka connector in file mode was 45 to 70 seconds. [V4]
8. Also, nobody on the team wants to operate a Kafka Connect cluster. [V4]
9. Approved by Elena Fischer and reviewed by James Owusu from Security & Compliance on 20 May 2026. [V5]

_Judge: offline word overlap 0.40_

### Q05: Which open tickets are blocking the Triton GA release, and who is each one assigned to?

**Gold:** Three open blockers: TRI-12 Migrate ledger-db to Aurora PostgreSQL (Alex Chen, In Progress), TRI-15 Fix Terraform state drift in prod VPC module (Sarah Jenkins, Open) and TRI-19 ArgoCD sync failures on auth-service (Tom Brooks, In Progress). TRI-8 also blocked Triton GA but is Done.

**graphrag** (answered, 473.8 ms, correctness 1.0, recall 1.0, strategy template:release_blockers):

1. Ticket TRI-12 (Migrate ledger-db to Aurora PostgreSQL with zero downtime) blocks Triton GA (target 2026-12-10); status In Progress (open); priority Highest; assigned to Alex Chen. [G1]
2. Ticket TRI-15 (Fix Terraform state drift in prod VPC module) blocks Triton GA (target 2026-12-10); status Open (open); priority High; assigned to Sarah Jenkins. [G2]
3. Ticket TRI-19 (ArgoCD sync failures on auth-service (CRD ordering)) blocks Triton GA (target 2026-12-10); status In Progress (open); priority High; assigned to Tom Brooks. [G3]
4. Ticket TRI-8 (EKS cluster baseline for prod) blocks Triton GA (target 2026-12-10); status Done (closed, no longer blocking); priority High; assigned to Sarah Jenkins. [G4]
5. Before Triton GA we cannot have only one person who knows how to operate ledger-db. [V1]
6. Slack #triton thread, 2026-10-13 09:05 UTC. [V1]
7. December 2026: Triton GA, with ledger-db and auth-service running on the new platform. [V2]
8. Knowledge of ledger-db internals is concentrated in Alex Chen, which is a key-person risk for Triton GA. [V2]
9. Project Triton moves the ledger platform from hand-managed EC2 hosts to Amazon EKS, with all infrastructure defined in Terraform and all deployments driven by ArgoCD. [V2]
10. TRI-15 blocks Triton GA, so I am treating it as high priority this sprint. [V3]
11. Slack #triton thread, 2026-09-29 08:12 UTC. [V3]
12. The rehearsal ran a blocking DDL statement against the production primary without locktimeout. [V4]
13. Write a ledger-db emergency runbook so more than one engineer can act (owner Alex Chen). [V4]

_Judge: offline word overlap 0.86_

**vector** (answered, 322.8 ms, correctness 0.0, recall 0.333, strategy -):

1. Before Triton GA we cannot have only one person who knows how to operate ledger-db. [V1]
2. Slack #triton thread, 2026-10-13 09:05 UTC. [V1]
3. December 2026: Triton GA, with ledger-db and auth-service running on the new platform. [V2]
4. Knowledge of ledger-db internals is concentrated in Alex Chen, which is a key-person risk for Triton GA. [V2]
5. Project Triton moves the ledger platform from hand-managed EC2 hosts to Amazon EKS, with all infrastructure defined in Terraform and all deployments driven by ArgoCD. [V2]
6. TRI-15 blocks Triton GA, so I am treating it as high priority this sprint. [V3]
7. Slack #triton thread, 2026-09-29 08:12 UTC. [V3]
8. The rehearsal ran a blocking DDL statement against the production primary without locktimeout. [V4]
9. Write a ledger-db emergency runbook so more than one engineer can act (owner Alex Chen). [V4]
10. Alex is a single point of failure for both Triton GA and Horizon. [V5]
11. Alex Chen: I am heads-down on the ledger-db migration for Triton. [V5]
12. Maria Garcia: That puts Horizon v3 GA on 20 November at risk. [V5]

_Judge: offline word overlap 0.26_

### Q06: Which tools has Linh Nguyen used across all of her projects?

**Gold:** On the Q2 2026 SOX Audit: AuditBoard and Snowflake. On Project Atlas: Snowflake, dbt, Airflow and Snowpipe Streaming.

**graphrag** (answered, 518.2 ms, correctness 1.0, recall 1.0, strategy template:person_projects_tools):

1. Linh Nguyen worked on Q2 2026 SOX Audit as Data Controls Analyst (2026-04-15 to 2026-06-30); that project uses Snowflake, AuditBoard. [G1]
2. Linh Nguyen worked on Project Atlas as Analytics Engineer (2026-07-01 to present); that project uses Snowflake, dbt, Airflow, Snowpipe Streaming. [G2]
3. Thanks Sarah Jenkins for the evidence automation and Linh Nguyen for the reconciliation tests. [V1]
4. Sarah moves to Triton next week and Linh joins Atlas. [V1]
5. Linh Nguyen: Ben Wright I am getting schema violations from payments.v1 events with major version 2. [V2]
6. Linh Nguyen joined in mid April to test the data controls around financial reporting tables. [V3]
7. After the audit, Sarah Jenkins moved to Project Triton and Linh Nguyen moved to Project Atlas. [V3]
8. Linh Nguyen joined the project in July 2026 after the Q2 audit. [V4]
9. The audit team was Raj Malhotra (lead), Sarah Jenkins (evidence automation) and Linh Nguyen (data controls). [V5]

_Judge: offline word overlap 1.00_

**vector** (answered, 334.6 ms, correctness 0.5, recall 0.0, strategy -):

1. Thanks Sarah Jenkins for the evidence automation and Linh Nguyen for the reconciliation tests. [V1]
2. Sarah moves to Triton next week and Linh joins Atlas. [V1]
3. Linh Nguyen: Ben Wright I am getting schema violations from payments.v1 events with major version 2. [V2]
4. Linh Nguyen joined in mid April to test the data controls around financial reporting tables. [V3]
5. After the audit, Sarah Jenkins moved to Project Triton and Linh Nguyen moved to Project Atlas. [V3]
6. Linh Nguyen joined the project in July 2026 after the Q2 audit. [V4]
7. The audit team was Raj Malhotra (lead), Sarah Jenkins (evidence automation) and Linh Nguyen (data controls). [V5]

_Judge: offline word overlap 0.42_

### Q07: Why did the data team choose Snowpipe Streaming over Kafka Connect?

**Gold:** Lower latency (p95 of 6 seconds versus 45 to 70 seconds for the file-based connector), fewer moving parts (no Kafka Connect cluster to run, which nobody on the team had operated), lower cost that scales with rows rather than files, and exactly-once loading through offset tokens.

**graphrag** (answered, 328.9 ms, correctness 1.0, recall 1.0, strategy -):

1. The two realistic options were the Snowflake Kafka Connector running on a Kafka Connect cluster, or lightweight consumers in the event-stream service that call the Snowpipe Streaming API directly. [V1]
2. Fewer moving parts: Kafka Connect would add a cluster to run, patch and monitor, and nobody on the Data Engineering team has operated one in production. [V1]
3. ADR-005: Snowpipe Streaming for event ingestion. [V1]
4. Producers write to topics on kafka-cluster, and a set of consumers loads the events into Snowflake with Snowpipe Streaming. [V2]
5. Each consumer commits Snowpipe Streaming offset tokens only after Snowflake acknowledges the rows, which gives exactly-once loading per channel. [V2]
6. Data Engineering owns event-stream. [V2]
7. Priya Patel: Benchmark results are in: Snowpipe Streaming p95 is 6 seconds; the Kafka connector in file mode was 45 to 70 seconds. [V3]
8. Also, nobody on the team wants to operate a Kafka Connect cluster. [V3]
9. SEV1: payments failing for more than 1% of requests, or any data integrity risk to the ledger. [V4]
10. The primary on-call engineer from the Payments Team acknowledges the page within 5 minutes and opens an incident channel named inc-<number>. [V4]
11. If ledger-db or auth-service is involved, page the Platform Team on-call immediately; do not wait for the 10-minute mark. [V4]
12. The Platform Team owns ledger-db. [V5]
13. On-call is shared by the Platform Team rotation. [V5]
14. A change data capture connector copies ledger entries to kafka-cluster (topic ledger.v1). [V5]

_Judge: offline word overlap 0.66_

**vector** (answered, 340.7 ms, correctness 1.0, recall 1.0, strategy -):

1. The two realistic options were the Snowflake Kafka Connector running on a Kafka Connect cluster, or lightweight consumers in the event-stream service that call the Snowpipe Streaming API directly. [V1]
2. Fewer moving parts: Kafka Connect would add a cluster to run, patch and monitor, and nobody on the Data Engineering team has operated one in production. [V1]
3. ADR-005: Snowpipe Streaming for event ingestion. [V1]
4. Producers write to topics on kafka-cluster, and a set of consumers loads the events into Snowflake with Snowpipe Streaming. [V2]
5. Each consumer commits Snowpipe Streaming offset tokens only after Snowflake acknowledges the rows, which gives exactly-once loading per channel. [V2]
6. Data Engineering owns event-stream. [V2]
7. Priya Patel: Benchmark results are in: Snowpipe Streaming p95 is 6 seconds; the Kafka connector in file mode was 45 to 70 seconds. [V3]
8. Also, nobody on the team wants to operate a Kafka Connect cluster. [V3]
9. SEV1: payments failing for more than 1% of requests, or any data integrity risk to the ledger. [V4]
10. The primary on-call engineer from the Payments Team acknowledges the page within 5 minutes and opens an incident channel named inc-<number>. [V4]
11. If ledger-db or auth-service is involved, page the Platform Team on-call immediately; do not wait for the 10-minute mark. [V4]
12. The Platform Team owns ledger-db. [V5]
13. On-call is shared by the Platform Team rotation. [V5]
14. A change data capture connector copies ledger entries to kafka-cluster (topic ledger.v1). [V5]

_Judge: offline word overlap 0.66_

### Q08: What was the root cause of the ledger-db outage in October 2026?

**Gold:** A TRI-12 migration rehearsal ran a blocking DDL statement against the production primary without lock_timeout. It took an ACCESS EXCLUSIVE lock that blocked all writes and exhausted the PgBouncer connection pool for 47 minutes. Detection was slow because the pool saturation alert went to a muted channel.

**graphrag** (answered, 350.1 ms, correctness 0.0, recall 0.25, strategy -):

1. October 2026: ledger-db migration rehearsal to Aurora PostgreSQL. [V1]
2. December 2026: Triton GA, with ledger-db and auth-service running on the new platform. [V1]
3. The October rehearsal caused the INC-142 outage and must be repeated. [V1]
4. Postmortem INC-142: ledger-db outage on 12 October 2026. [V2]
5. From 14:05 to 14:52 UTC on 12 October 2026, ledger-db refused new connections. [V2]
6. 14:21 Tom Brooks pages Alex Chen, the ledger-db owner. [V2]
7. Alex Chen joined as a platform advisor in August 2026 because payments-api depends on ledger-db and auth-service. [V3]
8. payments-api writes every transaction to ledger-db and validates tokens through auth-service. [V3]
9. Postmortem INC-118: payments-api latency spike on 3 August 2026. [V4]
10. Q2 2026 SOX Audit sign-off memo. [V5]
11. The Q2 2026 SOX audit of the ledger platform IT general controls is complete. [V5]
12. Logical access to ledger-db and auth-service (privileged and standard roles). [V5]

_Judge: offline word overlap 0.16_

**vector** (answered, 324.5 ms, correctness 0.0, recall 0.25, strategy -):

1. October 2026: ledger-db migration rehearsal to Aurora PostgreSQL. [V1]
2. December 2026: Triton GA, with ledger-db and auth-service running on the new platform. [V1]
3. The October rehearsal caused the INC-142 outage and must be repeated. [V1]
4. Postmortem INC-142: ledger-db outage on 12 October 2026. [V2]
5. From 14:05 to 14:52 UTC on 12 October 2026, ledger-db refused new connections. [V2]
6. 14:21 Tom Brooks pages Alex Chen, the ledger-db owner. [V2]
7. Alex Chen joined as a platform advisor in August 2026 because payments-api depends on ledger-db and auth-service. [V3]
8. payments-api writes every transaction to ledger-db and validates tokens through auth-service. [V3]
9. Postmortem INC-118: payments-api latency spike on 3 August 2026. [V4]
10. Q2 2026 SOX Audit sign-off memo. [V5]
11. The Q2 2026 SOX audit of the ledger platform IT general controls is complete. [V5]
12. Logical access to ledger-db and auth-service (privileged and standard roles). [V5]

_Judge: offline word overlap 0.16_

### Q09: What is the escalation process for a SEV1 on payments-api?

**Gold:** Primary on-call acknowledges within 5 minutes and opens an incident channel; within 10 minutes page the secondary on-call and the escalation manager Maria Garcia; page Platform on-call immediately if ledger-db or auth-service is involved; inform VP Engineering Elena Fischer if the SEV1 lasts over 30 minutes; customer support posts a status page update within 15 minutes.

**graphrag** (answered, 329.1 ms, correctness 0.5, recall 0.4, strategy -):

1. payments-api is the public REST API that merchants and partners call to create payments, refunds and payouts. [V1]
2. The Payments Team owns payments-api. [V1]
3. Maria Garcia is the escalation manager. [V1]
4. The escalation manager informs the VP Engineering, Elena Fischer, for any SEV1 lasting longer than 30 minutes. [V2]
5. payments-api on-call runbook. [V2]
6. SEV1: payments failing for more than 1% of requests, or any data integrity risk to the ledger. [V2]
7. Tom Brooks: SEV1 declared: ledger-db is refusing new connections and payments-api is returning 503. [V3]
8. Ben Wright is the primary owner and Priya Patel is the escalation contact. [V4]
9. payments.v1: payment lifecycle events from payments-api. [V4]

_Judge: offline word overlap 0.39_

**vector** (answered, 333.3 ms, correctness 0.5, recall 0.4, strategy -):

1. payments-api is the public REST API that merchants and partners call to create payments, refunds and payouts. [V1]
2. The Payments Team owns payments-api. [V1]
3. Maria Garcia is the escalation manager. [V1]
4. The escalation manager informs the VP Engineering, Elena Fischer, for any SEV1 lasting longer than 30 minutes. [V2]
5. payments-api on-call runbook. [V2]
6. SEV1: payments failing for more than 1% of requests, or any data integrity risk to the ledger. [V2]
7. Tom Brooks: SEV1 declared: ledger-db is refusing new connections and payments-api is returning 503. [V3]
8. Ben Wright is the primary owner and Priya Patel is the escalation contact. [V4]
9. payments.v1: payment lifecycle events from payments-api. [V4]

_Judge: offline word overlap 0.39_

### Q10: Who has the most open tickets on Project Atlas, and what are they?

**Gold:** Ben Wright has the most open tickets on Project Atlas: 3 (ATL-3 Consumer for the payments.v1 topic, ATL-5 Snowpipe Streaming offset token checkpointing, ATL-7 Dead letter handling for schema violations). Linh Nguyen and Priya Patel have one each (ATL-4, ATL-9).

**graphrag** (answered, 510.2 ms, correctness 1.0, recall 1.0, strategy template:project_open_ticket_load):

1. On Project Atlas, Ben Wright has 3 open ticket(s): ATL-3 Consumer for the payments.v1 topic [Open]; ATL-5 Snowpipe Streaming offset token checkpointing [In Progress]; ATL-7 Dead letter handling for schema violations [Open]. [G1]
2. On Project Atlas, Linh Nguyen has 1 open ticket(s): ATL-4 Finance mart: daily account balances [Open]. [G2]
3. On Project Atlas, Priya Patel has 1 open ticket(s): ATL-9 Data retention policy for raw events [In Review]. [G3]
4. After the audit, Sarah Jenkins moved to Project Triton and Linh Nguyen moved to Project Atlas. [V1]
5. Project Atlas builds Fintara's near real-time data platform. [V2]
6. Linh Nguyen joined the project in July 2026 after the Q2 audit. [V2]
7. Priya Patel leads the project and owns the architecture. [V2]
8. Project Triton moves the ledger platform from hand-managed EC2 hosts to Amazon EKS, with all infrastructure defined in Terraform and all deployments driven by ArgoCD. [V3]
9. The infrastructure stack chosen for the Triton deployment is managed through Terraform modules authored by Sarah Jenkins after she joined the project in July 2026. [V3]
10. March 2026: project kickoff, landing zone design. [V3]
11. Slack #atlas thread, 2026-09-22 10:00 UTC. [V4]

_Judge: offline word overlap 0.90_

**vector** (answered, 355.0 ms, correctness 0.0, recall 0.0, strategy -):

1. After the audit, Sarah Jenkins moved to Project Triton and Linh Nguyen moved to Project Atlas. [V1]
2. Project Atlas builds Fintara's near real-time data platform. [V2]
3. Linh Nguyen joined the project in July 2026 after the Q2 audit. [V2]
4. Priya Patel leads the project and owns the architecture. [V2]
5. Project Triton moves the ledger platform from hand-managed EC2 hosts to Amazon EKS, with all infrastructure defined in Terraform and all deployments driven by ArgoCD. [V3]
6. The infrastructure stack chosen for the Triton deployment is managed through Terraform modules authored by Sarah Jenkins after she joined the project in July 2026. [V3]
7. March 2026: project kickoff, landing zone design. [V3]
8. Slack #atlas thread, 2026-09-22 10:00 UTC. [V4]

_Judge: offline word overlap 0.23_
