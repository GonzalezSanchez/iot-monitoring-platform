# Project 2a — Behavior Pattern Analyzer

ETL pipeline that reads historical sensor data from Project 1a (DynamoDB) and detects behavioral patterns and anomalies across rooms over time. Scheduled batch processing via EventBridge + Step Functions, results stored in Aurora Serverless v2 and exposed via REST API.

## Stack

- **Runtime:** Python 3.11
- **Infrastructure:** Terraform
- **AWS Services:** Lambda, Step Functions, EventBridge Scheduler, Aurora Serverless v2, API Gateway (HTTP), Secrets Manager, VPC Endpoints
- **Database:** Aurora PostgreSQL 15.10 (Serverless v2 — scales to zero when idle)
- **Testing:** pytest (unit + integration + regression), moto for DynamoDB mocking

## Architecture

```
EventBridge Scheduler (weekly)
        │
        ▼
Step Functions — ETL Pipeline
        │
        ├── Extract Lambda   → reads DynamoDB SensorEvents (project 1a)
        │                      deduplicates, inserts into raw_sensor_data
        │
        ├── Transform Lambda → validates readings (temp range, null checks)
        │                      deletes invalid rows
        │
        └── Analyze Lambda   → detects patterns + anomalies
                               writes to patterns / anomalies tables

API Gateway (HTTP)
        ├── POST /analyze/patterns              → starts ETL execution
        ├── GET  /analyze/patterns/{job_id}     → returns patterns for a job
        └── GET  /insights/{entity_type}/{id}   → returns patterns + anomalies per entity
```

## Key Design Decisions

**No NAT Gateway** — Lambda functions reach AWS APIs via VPC Endpoints instead of a NAT Gateway. Three endpoints are used: DynamoDB (Gateway, free), Secrets Manager (Interface), and CloudWatch Logs (Interface). The CloudWatch Logs endpoint is required — Lambda inside a private subnet cannot reach CloudWatch without it. Traffic stays within the AWS network (security + lower latency) and costs ~$14/month vs ~$32/month for a NAT Gateway.

**Aurora Serverless v2 with auto-pause** — scales between 0.5–2 ACU, pauses after inactivity. Cold start ~5 seconds, acceptable for a scheduled batch pipeline.

**Deploy/destroy strategy** — infrastructure is provisioned on demand for demos and destroyed afterwards. Cost while deployed: ~$15/month. Cost while destroyed: $0.

**Least-privilege IAM** — Lambda role has read-only access to DynamoDB, read-only access to its specific Secrets Manager secret, and scoped Step Functions permissions.

## Patterns Detected

- `occupancy_schedule` — typical occupied hours per room per weekday
- `temperature_trend` — rising / falling / stable mean temperature over the window

## Anomalies Detected

- `temperature_spike` — reading > mean + 3σ for that room
- `unusual_activity` — motion detected outside the typical occupancy schedule

## Database Schema

```sql
-- Raw readings ingested from DynamoDB
CREATE TABLE raw_sensor_data (
    id            BIGSERIAL     PRIMARY KEY,
    event_id      TEXT          NOT NULL UNIQUE,
    device_id     TEXT          NOT NULL,
    room_id       TEXT          NOT NULL,
    ts            TIMESTAMPTZ   NOT NULL,
    temperature   DOUBLE PRECISION,
    humidity      DOUBLE PRECISION,
    motion        BOOLEAN,
    occupancy     BOOLEAN,
    raw_payload   JSONB         NOT NULL,
    ingested_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- Behavioral patterns per entity (room / device)
CREATE TABLE patterns (
    id            BIGSERIAL     PRIMARY KEY,
    job_id        TEXT          NOT NULL,
    entity_type   TEXT          NOT NULL,
    entity_id     TEXT          NOT NULL,
    pattern_type  TEXT          NOT NULL,
    period_start  TIMESTAMPTZ   NOT NULL,
    period_end    TIMESTAMPTZ   NOT NULL,
    data          JSONB         NOT NULL,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- Anomalies per entity
CREATE TABLE anomalies (
    id            BIGSERIAL     PRIMARY KEY,
    job_id        TEXT          NOT NULL,
    entity_type   TEXT          NOT NULL,
    entity_id     TEXT          NOT NULL,
    anomaly_type  TEXT          NOT NULL,
    detected_at   TIMESTAMPTZ   NOT NULL,
    severity      TEXT          NOT NULL,  -- low | medium | high
    data          JSONB         NOT NULL,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
```

## API Endpoints

### POST /analyze/patterns
Starts a new ETL execution for a given time window.

```json
// Request
{ "days_back": 7 }

// Response 202
{ "job_id": "uuid", "execution_arn": "arn:aws:states:..." }
```

### GET /analyze/patterns/{job_id}
Returns all patterns detected for a given ETL job.

```json
{
  "job_id": "uuid",
  "patterns": [
    {
      "entity_type": "room",
      "entity_id": "room-a",
      "pattern_type": "occupancy_schedule",
      "data": { "schedule": { "0": [9, 10, 11] } },
      "period_start": "2026-01-01T00:00:00Z",
      "period_end": "2026-01-07T23:59:59Z"
    }
  ]
}
```

### GET /insights/{entity_type}/{entity_id}
Returns all patterns and anomalies for a room or device.

```json
{
  "entity_type": "room",
  "entity_id": "room-a",
  "patterns": [ ... ],
  "anomalies": [ ... ]
}
```

## Infrastructure

Provisioned via Terraform in `infrastructure/`:

| File | What it creates |
|---|---|
| `vpc.tf` | VPC, private subnets, security groups, VPC endpoints |
| `database.tf` | Aurora Serverless v2 cluster + instance |
| `iam.tf` | Lambda, Step Functions, EventBridge roles |
| `secrets.tf` | Secrets Manager secret for DB credentials |
| `lambdas.tf` | 6 Lambda functions + dependency layer |
| `stepfunctions.tf` | ETL state machine (Extract → Transform → Analyze) |
| `apigateway.tf` | HTTP API with 3 routes |
| `eventbridge.tf` | Weekly scheduler (Sunday 02:00 UTC) |

## Usage

```bash
cd backend/project2a-behavior-analyzer

# Start lokale PostgreSQL database
docker compose -f docker/docker-compose.yml up -d

# Run DB migrations (once after deploy)
python scripts/migrate.py

# Deploy infrastructure
./scripts/deploy.sh prod

# Tear down after demo
./scripts/destroy.sh prod
```

## Testing

```bash
# Unit tests (no AWS needed)
pytest tests/unit/

# Integration tests (requires Docker PostgreSQL)
docker-compose up -d
pytest tests/integration/

# Coverage
pytest --cov=lambdas tests/unit/
```
