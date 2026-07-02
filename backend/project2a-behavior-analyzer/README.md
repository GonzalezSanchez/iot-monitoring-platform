# Project 2a — Behavior Pattern Analyzer (AWS native)

## Beschrijving

ETL pipeline die historische sensor data uit project 1a (DynamoDB) leest, gedragspatronen en anomalieën detecteert per kamer, en de resultaten opslaat in Aurora PostgreSQL. Resultaten zijn opvraagbaar via een REST API.

## Deployment

Deployed on-demand for demos — infrastructure is destroyed after each session to minimise AWS costs (Aurora Serverless v2 has a minimum cost even when idle).

To deploy: `cd infrastructure && terraform apply`
To destroy: `cd infrastructure && terraform destroy`

## Tech Stack

- **Runtime:** Python 3.13
- **Cloud Services:** AWS Lambda, Step Functions, EventBridge, Aurora Serverless v2 (PostgreSQL), Secrets Manager, API Gateway
- **Database:** Aurora Serverless v2 (PostgreSQL — scales to zero when idle)
- **IaC:** Terraform
- **Containerization:** Docker (lokale ontwikkeling + CI)
- **Testing:** pytest (unit, integration, regression)
- **CI/CD:** GitHub Actions

## Features

- ETL pipeline: Extract (DynamoDB → Aurora) → Transform (validatie + normalisatie) → Analyze (pattern + anomaly detection)
- Pattern detection: `occupancy_schedule`, `temperature_trend`
- Anomaly detection: `temperature` (z ≥ 3σ → medium, z ≥ 5σ → high, populatie stddev), `unusual_activity` (beweging buiten typische bezettingsuren, medium)
- Scheduled batch processing via EventBridge + Step Functions
- REST API voor het ophalen van resultaten per entity

## API Endpoints

### POST /analyze/patterns
Start een nieuwe ETL-job voor een tijdvenster.

**Request:**
```json
{
  "days_back": 7
}
```

`days_back` is optioneel (default: 7).

**Response (202):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "execution_arn": "arn:aws:states:eu-central-1:123456789:execution:..."
}
```

---

### GET /analyze/patterns/{job_id}
Haal alle gedetecteerde patterns op voor een specifieke job.

**Response (200):**
```json
{
  "job_id": "550e8400-...",
  "patterns": [
    {
      "job_id": "550e8400-...",
      "entity_type": "room",
      "entity_id": "conference-a1",
      "pattern_type": "occupancy_schedule",
      "data": { "typical_hours": { "Monday": [9, 17] } },
      "period_start": "2026-01-06T00:00:00Z",
      "period_end": "2026-01-13T00:00:00Z"
    }
  ]
}
```

---

### GET /insights/{entity_type}/{entity_id}
Haal alle patterns en anomalieën op voor één entity (kamer of device).

**Response (200):**
```json
{
  "entity_type": "room",
  "entity_id": "conference-a1",
  "patterns": [
    {
      "job_id": "...",
      "entity_type": "room",
      "entity_id": "conference-a1",
      "pattern_type": "occupancy_schedule",
      "data": { ... },
      "period_start": "2026-01-06T00:00:00Z",
      "period_end": "2026-01-13T00:00:00Z"
    }
  ],
  "anomalies": [
    {
      "job_id": "...",
      "entity_type": "room",
      "entity_id": "conference-a1",
      "anomaly_type": "temperature",
      "detected_at": "2026-01-10T14:00:00Z",
      "severity": "high",
      "data": { "temperature": 38.2, "mean": 22.1, "stddev": 1.8, "z_score": 5.2 }
    }
  ]
}
```

## Database Schema (Aurora PostgreSQL)

**Table:** `rooms` *(statische referentietabel — gevuld via `seed_rooms.py`)*
```sql
CREATE TABLE rooms (
    room_id       TEXT             PRIMARY KEY,
    building_id   TEXT             NOT NULL,
    building_name TEXT             NOT NULL,
    floor         INTEGER,
    lat           DOUBLE PRECISION NOT NULL,
    lon           DOUBLE PRECISION NOT NULL
);
```

**Table:** `raw_sensor_data`
```sql
CREATE TABLE raw_sensor_data (
    id          BIGSERIAL    PRIMARY KEY,
    event_id    TEXT         NOT NULL UNIQUE,
    device_id   TEXT         NOT NULL,
    room_id     TEXT         NOT NULL,
    ts          TIMESTAMPTZ  NOT NULL,
    temperature DOUBLE PRECISION,
    humidity    DOUBLE PRECISION,
    motion      BOOLEAN,
    occupancy   BOOLEAN,
    raw_payload JSONB        NOT NULL,
    ingested_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
```

**Table:** `patterns`
```sql
CREATE TABLE patterns (
    id           BIGSERIAL   PRIMARY KEY,
    job_id       TEXT        NOT NULL,
    entity_type  TEXT        NOT NULL,  -- 'room' | 'device'
    entity_id    TEXT        NOT NULL,
    pattern_type TEXT        NOT NULL,  -- 'occupancy_schedule' | 'temperature_trend'
    period_start TIMESTAMPTZ NOT NULL,
    period_end   TIMESTAMPTZ NOT NULL,
    data         JSONB       NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Table:** `anomalies`
```sql
CREATE TABLE anomalies (
    id           BIGSERIAL   PRIMARY KEY,
    job_id       TEXT        NOT NULL,
    entity_type  TEXT        NOT NULL,  -- 'room' | 'device'
    entity_id    TEXT        NOT NULL,
    anomaly_type TEXT        NOT NULL,  -- 'temperature' | 'unusual_activity'
    detected_at  TIMESTAMPTZ NOT NULL,
    severity     TEXT        NOT NULL,  -- 'medium' | 'high'
    data         JSONB       NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## Architectuur

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

**ETL stappen:**

1. **Extract** — leest SensorEvents uit DynamoDB (project 1a) voor het opgegeven tijdvenster, schrijft naar `raw_sensor_data`
2. **Transform** — valideert en normaliseert de ruwe data (deduplicatie, type casting)
3. **Analyze** — detecteert patterns en anomalieën per kamer, schrijft naar `patterns` en `anomalies`

## Screenshots

### Execution history — 7 runs, all Succeeded

![Step Functions executions](../../docs/screenshots/project2-step-functions/project2a-step-functions-executions.png)

### Behavior Pattern Analyzer dashboard — occupancy schedules and temperature trends per room

![Behavior dashboard](../../docs/screenshots/project2-step-functions/project2a-behavior-dashboard.png)

## Security

Intentionally excluded from this project — see [Project 3: IoT Device Gateway](project3-iot-gateway.md) for authentication with JWT via Cognito.

Aurora credentials worden beheerd via AWS Secrets Manager (productie) of `.env` (lokaal).

## Installatie & Gebruik

```bash
cd backend/project2a-behavior-analyzer

# Lokale database opzetten (PostgreSQL via Docker)
docker-compose up -d db

# Database migraties uitvoeren
python scripts/migrate.py

# Kamers seeden met gebouwen en coördinaten
python scripts/seed_rooms.py

# Deploy naar AWS (Terraform)
cd infrastructure
terraform init
terraform apply

# Handmatig een analyse starten
curl -X POST https://<api-gateway-url>/analyze/patterns \
  -H "Content-Type: application/json" \
  -d '{"days_back": 7}'
```

## Testing

```bash
# Unit tests (gemockte AWS + DB)
pytest tests/unit/

# Integration tests (vereist lokale PostgreSQL)
pytest tests/integration/

# Regression tests
pytest tests/regression/

# Coverage
pytest --cov=lambdas tests/
```
