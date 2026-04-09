# Project 2a — Build Order

```
Project 2a — Build Order
═══════════════════════════════════════════════════════════

Phase 1: Foundation
───────────────────
  [1] Folder structure
       backend/project2a-behavior-analyzer/
       ├── lambdas/
       ├── infrastructure/
       ├── tests/
       └── scripts/

  [2] Infrastructure — Terraform
       ├── VPC + subnets + security groups
       ├── Aurora Serverless v2 cluster
       ├── Lambda execution role (IAM)
       └── Secrets Manager (DB credentials)

Phase 2: Database
─────────────────
  [3] DB migration script (Python)
       └── creates: raw_sensor_data, patterns, anomalies

Phase 3: ETL Lambdas
────────────────────
  [4] Lambda: Extract
       └── DynamoDB prod-SensorEvents → raw_sensor_data

  [5] Lambda: Transform
       └── normalize + clean raw_sensor_data

  [6] Lambda: Analyze
       └── pattern detection + anomaly detection
       └── writes → patterns, anomalies

Phase 4: Orchestration
───────────────────────
  [7] Step Functions state machine
       Extract → Transform → Analyze (sequential)

  [8] EventBridge rule
       └── triggers Step Functions on schedule

Phase 5: REST API
─────────────────
  [9] API Lambdas
       ├── POST /analyze/patterns
       ├── GET  /analyze/patterns/{job_id}
       └── GET  /insights/{entity_type}/{entity_id}

  [10] API Gateway
        └── routes → Lambda handlers

Phase 6: Tests + CI/CD
───────────────────────
  [11] Unit tests (mocked DB)
  [12] Integration tests (local PostgreSQL via Docker)
  [13] Extend deploy.yml for project 2a

═══════════════════════════════════════════════════════════
Dependencies:
  1 → 2 → 3 → 4 → 5 → 6 → 7 → 8  (ETL pipeline, sequential)
  3 → 9 → 10                        (API, needs DB schema)
  all → 11 → 12 → 13               (tests last)
```
