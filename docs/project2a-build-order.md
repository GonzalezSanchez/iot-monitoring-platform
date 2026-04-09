# Project 2a — Build Order

```
Project 2a — Build Order
═══════════════════════════════════════════════════════════

Rule: tests worden geschreven PARALLEL aan de code, niet achteraf.
      Elke fase eindigt met groene tests voor commit.

Phase 1: Foundation
───────────────────
  [1] Folder structure + CI setup
       backend/project2a-behavior-analyzer/
       ├── lambdas/
       ├── infrastructure/
       ├── tests/
       └── scripts/
       └── .github/workflows/ci.yml

  [2] Infrastructure — Terraform
       ├── VPC + subnets + security groups
       ├── Aurora Serverless v2 cluster
       ├── Lambda execution role (IAM)
       └── Secrets Manager (DB credentials)

Phase 2: Database
─────────────────
  [3] DB migration script (Python)
       └── creates: raw_sensor_data, patterns, anomalies
  [3t] Tests: migrate.py
       ├── tabellen bestaan na run (local Docker PostgreSQL)
       └── tweede run gooit geen error (idempotent)

Phase 3: ETL Lambdas
────────────────────
  [4] Lambda: Extract
       └── DynamoDB prod-SensorEvents → raw_sensor_data
  [4t] Tests: extract
       ├── DynamoDB scan gemocked (moto)
       ├── correcte rows geïnsert
       └── duplicaten geskipt (ON CONFLICT DO NOTHING)

  [5] Lambda: Transform
       └── normalize + clean raw_sensor_data
  [5t] Tests: transform
       ├── ongeldige temperaturen verwijderd
       └── valide rijen blijven

  [6] Lambda: Analyze
       └── pattern detection + anomaly detection
       └── writes → patterns, anomalies
  [6t] Tests: analyze
       ├── detect_occupancy_schedule: bekende input → verwachte schedule
       ├── detect_temperature_trend: stijgende reeks → 'rising'
       ├── detect_temperature_spikes: z-score ≥ 3 → anomalie
       └── detect_unusual_activity: motion buiten schedule → anomalie

Phase 4: Orchestration
───────────────────────
  [7] Step Functions state machine + Terraform (lambdas.tf, stepfunctions.tf)
       Extract → Transform → Analyze (sequential)
  [8] EventBridge rule (eventbridge.tf)
       └── triggers Step Functions wekelijks

Phase 5: REST API
─────────────────
  [9] API Lambdas
       ├── POST /analyze/patterns
       ├── GET  /analyze/patterns/{job_id}
       └── GET  /insights/{entity_type}/{entity_id}
  [9t] Tests: API handlers (mocked DB)

  [10] API Gateway Terraform resource
        └── routes → Lambda handlers

Phase 6: CI/CD
──────────────
  [11] Integration tests (local PostgreSQL via Docker)
  [12] Extend deploy.yml for project 2a

═══════════════════════════════════════════════════════════
Dependencies:
  1 → 2 → 3+3t → 4+4t → 5+5t → 6+6t → 7 → 8  (ETL pipeline)
  3 → 9+9t → 10                                  (API, needs DB schema)
  all → 11 → 12                                  (integration tests last)
```
