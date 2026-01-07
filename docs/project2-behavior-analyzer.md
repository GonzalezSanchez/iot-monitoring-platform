# Project 2: Behavior Pattern Analyzer

## Beschrijving

ETL pipeline voor detectie van gedragspatronen en anomalieën uit sensor data. Gebruikt machine learning voor pattern recognition en voorspellende analytics.

## Tech Stack

- **Runtime:** Python 3.11
- **Cloud Services:** AWS Lambda, RDS PostgreSQL, Step Functions, S3
- **Database:** PostgreSQL 15+
- **Containerization:** Docker
- **Testing:** pytest

## Features

- ETL pipeline voor data processing
- Pattern detection algoritmes
- Anomaly detection
- Behavioral insights generation
- Scheduled batch processing
- REST API voor insights

## API Endpoints

### POST /analyze/patterns
Start een nieuwe pattern analysis job

**Request:**
```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-01-07",
  "entity_type": "room",
  "entity_ids": ["conference-a1", "conference-b2"]
}
```

**Response:**
```json
{
  "job_id": "uuid-here",
  "status": "processing"
}
```

### GET /analyze/patterns/{job_id}
Haal job status en resultaten op

### GET /insights/{entity_type}/{entity_id}
Haal behavioral insights op

**Response:**
```json
{
  "entity_id": "conference-a1",
  "patterns": [
    {
      "pattern_type": "occupancy_schedule",
      "confidence": 0.92,
      "description": "Typically occupied Mon-Fri 09:00-17:00",
      "detected_at": "2026-01-07T10:00:00Z"
    }
  ],
  "anomalies": [
    {
      "anomaly_type": "unusual_temperature",
      "severity": "medium",
      "timestamp": "2026-01-06T23:00:00Z",
      "description": "Temperature spike outside normal range"
    }
  ]
}
```

## Database Schema (PostgreSQL)

**Table:** raw_sensor_data
```sql
CREATE TABLE raw_sensor_data (
    id UUID PRIMARY KEY,
    entity_id VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    data JSONB NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_entity_timestamp (entity_id, timestamp),
    INDEX idx_processed (processed)
);
```

**Table:** patterns
```sql
CREATE TABLE patterns (
    id UUID PRIMARY KEY,
    entity_id VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    pattern_type VARCHAR(100) NOT NULL,
    confidence DECIMAL(3,2) NOT NULL,
    pattern_data JSONB NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_entity (entity_id, entity_type)
);
```

**Table:** anomalies
```sql
CREATE TABLE anomalies (
    id UUID PRIMARY KEY,
    entity_id VARCHAR(100) NOT NULL,
    anomaly_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    details JSONB NOT NULL,
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_entity_timestamp (entity_id, timestamp),
    INDEX idx_resolved (resolved)
);
```

## Architectuur

```
EventBridge (Scheduled) → Step Functions
                              ↓
                    Lambda (Extract) → RDS PostgreSQL
                              ↓           (raw_sensor_data)
                    Lambda (Transform)
                              ↓
                    Lambda (Analyze) → RDS PostgreSQL
                                       (patterns, anomalies)
```

## Installatie & Gebruik

```bash
cd backend/project2-behavior-analyzer

# Build Docker image
docker build -t behavior-analyzer .

# Run database migrations
python scripts/migrate.py

# Run lokaal
docker run -p 8000:8000 behavior-analyzer

# Deploy naar AWS
./deploy.sh
```

## Testing

```bash
# Unit tests
pytest tests/unit/

# Integration tests (requires PostgreSQL)
pytest tests/integration/

# Coverage report
pytest --cov=src tests/
```
