# Project 2a: Behavior Pattern Analyzer (AWS native)

## Description

ETL pipeline that reads historical sensor data from project 1a (DynamoDB), detects
behavior patterns and anomalies per room, and stores the results in Aurora
PostgreSQL, queryable via a REST API. It is the AWS-native half of a deliberate
pair: [project 2b](project2b-behavior-analyzer.md) solves the same analytics
problem with a data-engineering stack (Airflow + PySpark), so the two projects
demonstrate that the same business logic can be carried by very different tools.

| Aspect | Project 2a (AWS native) | Project 2b (Data Engineering) |
|--------|------------------------|-------------------------------|
| Orchestration | AWS Step Functions | Apache Airflow |
| Processing | Python (pandas) | PySpark (distributed) |
| Intermediate storage | Aurora Serverless v2 | S3 Parquet (data lake) |
| Serving layer | Aurora Serverless v2 | PostgreSQL (self-hosted Docker) |
| Visualization | REST API | Power BI (DirectQuery on PostgreSQL) |
| Lifecycle | Deploy/destroy on demand | Always-on (home server) |

## Status

**Not live by design.** Aurora Serverless v2 has a minimum cost even when idle
(~€15–20/month), so the stack is deployed for demos with `terraform apply` and
destroyed afterwards. Redeploy checklist: `scripts/README.md` in the project
(API Gateway URL changes per deploy — the frontend secret must be updated).

## Tech Stack

- **Runtime:** Python 3.13 (Lambda)
- **Cloud services:** Step Functions, EventBridge, Aurora Serverless v2
  (PostgreSQL), Secrets Manager, API Gateway
- **IaC:** Terraform
- **Testing:** pytest (unit, integration, regression)
- **CI:** GitHub Actions

## Architecture

```
EventBridge (Scheduled) ──► Step Functions
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
             Lambda (Extract) → Lambda (Transform) → Lambda (Analyze)
                    │                                      │
                    ▼                                      ▼
             DynamoDB                              Aurora PostgreSQL
             (project 1a)                         (patterns, anomalies)

API Gateway ──► Lambda (POST /analyze/patterns)  → Step Functions (start execution)
            ──► Lambda (GET  /analyze/patterns/{job_id}) → Aurora PostgreSQL
            ──► Lambda (GET  /insights/{entity_type}/{entity_id}) → Aurora PostgreSQL
```

## Key Design Decisions

**Step Functions for orchestration** — the ETL chain (Extract → Transform →
Analyze) is a state machine, not a cron script: each step is visible, retryable,
and its execution history is auditable in the console. The 2b mirror of this
decision is an Airflow DAG.

**Aurora Serverless v2 as both staging and serving layer** — one database plays
the role that 2b splits over S3 Parquet (staging) and PostgreSQL (serving).
Simpler topology, but it couples storage cost to compute availability — the
reason this project is deploy/destroy while 2b runs always-on.

**Deploy/destroy lifecycle** — infrastructure only exists during demos.
Consequences are documented rather than hidden: `deletion_protection` must be
flipped before a destroy, and the API Gateway URL (and the frontend secret
pointing at it) changes every redeploy.

**Anomaly detection with population statistics** — temperature anomalies use
z-scores on the population stddev (z ≥ 3σ → medium, z ≥ 5σ → high);
`unusual_activity` flags motion outside the room's typical occupancy hours.
The same statistical approach returns in 2b (PySpark) and 2c (dbt), which makes
the three implementations comparable.

**Secrets Manager for database credentials** — Lambdas fetch Aurora credentials
at runtime; nothing sensitive lives in environment variables or code.

## API & Data Model

Three endpoints (`POST /analyze/patterns`, `GET /analyze/patterns/{job_id}`,
`GET /insights/{entity_type}/{entity_id}`) over four tables (`rooms`,
`raw_sensor_data`, `patterns`, `anomalies`). Full request/response examples and
DDL: [project README](../backend/project2a-behavior-analyzer/README.md).

## Security

Authentication is intentionally out of scope here — the device/auth layer is
project 3's responsibility (see [project3a spec](project3a-iot-gateway.md) for
the AWS-native design with Cognito). Aurora credentials go through Secrets
Manager in production.

## Testing

Three test layers (unit with mocked AWS/DB, integration against local
PostgreSQL, regression), 98 tests in CI. Commands: see the
[project README](../backend/project2a-behavior-analyzer/README.md#testing).
