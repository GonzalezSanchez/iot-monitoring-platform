# Project 2b — Behavior Pattern Analyzer (Data Engineering stack)

## Description

ETL pipeline that extracts, transforms, and analyzes sensor data from project 1a (DynamoDB) via PySpark. Detects behavior patterns and anomalies per room and writes results to PostgreSQL. Visualized in Power BI.

Same analytical goal as project 2a — deliberately reimplemented with a Data Engineering stack to show the contrast: AWS native (Lambda + Step Functions) vs. PySpark + Airflow.

## Stack

- **Processing:** PySpark 4.x (Spark SQL, window functions, `regr_slope`)
- **Spatial analysis:** GeoPandas + Shapely (anomaly hotspots per building, WGS84 coordinates)
- **Reporting layer:** dbt (staging views + marts for Power BI)
- **Orchestration:** Apache Airflow 2.x (DAG met BashOperators)
- **Storage:** AWS S3 (data lake — raw + processed Parquet), PostgreSQL (resultaten)
- **Visualization:** Power BI (direct connect op PostgreSQL — map visual, bar charts, heatmap)
- **Observability:** OpenTelemetry (custom job metrics + Airflow StatsD) → OTel Collector → Grafana Cloud (Mimir metrics + Loki logs), postgres-exporter voor PostgreSQL metrics
- **IaC:** Terraform (S3 bucket + IAM)
- **CI/CD:** GitHub Actions (CI) + Jenkins (CD)
- **Testing:** pytest + PySpark in-process

## Data Lake Architecture

Three layers on S3 (Medallion architecture):

```
DynamoDB (prod-SensorEvents)
    │
    ▼  jobs/extract.py  (spark-submit)
S3/raw        ← Bronze: raw Parquet, partitioned by year/month
    │
    ▼  jobs/transform.py  (spark-submit)
S3/processed  ← Silver: validated and cleaned Parquet
    │
    ▼  jobs/analyze.py  (spark-submit)
PostgreSQL    ← Gold: patterns + anomalies (for Power BI)
    │
    ▼  jobs/spatial.py  (GeoPandas)
PostgreSQL    ← Spatial: anomaly hotspots per building (for Power BI map visual)
    │
    ▼  dbt run  (dbt-postgres)
PostgreSQL    ← Marts: anomaly_detail, pattern_detail, building_summary (Power BI-ready tables)
```

Idempotent: `partitionOverwriteMode=dynamic` — re-running only overwrites the affected month partitions.

## Design Decisions

**The Bronze layer holds normalized Parquet, not raw JSON**

In a strict Medallion architecture, Bronze would preserve the DynamoDB items as raw JSON — exactly as the source delivers them. Here, `extract.py` already writes to Bronze as Parquet, after a light normalization of two event formats (project 2b seed format + project 1b API format) into one unified schema.

Trade-off: Parquet is compressed and efficiently readable by Spark. Raw JSON in Bronze would allow full reprocessing in case of a bug in extraction — that's not possible here. For a portfolio with a limited dataset this is acceptable; in production I would keep Bronze as raw JSON.

**The Gold layer lives in PostgreSQL, not on S3**

`analyze.py` writes patterns and anomalies to PostgreSQL via JDBC instead of to S3 Gold. Reason: Power BI connects more easily to a SQL database than to S3 + Athena. In a fully AWS-native setup, Gold would sit as Parquet on S3 with Athena as the query layer.

## Airflow DAG

`dags/behavior_pipeline.py` — weekly every Monday at 02:00:

```
manage_partitions >> extract >> transform >> analyze >> spatial >> dbt_run
```

- `on_failure_callback` logs an `[ALERT]` after all retries are exhausted
- `SPARK_MASTER` configurable via env var (default: `local[*]`)

## Features

- Occupancy schedule detection — average occupancy rate per (room, day, hour) via window aggregation
- Temperature trend — rising/falling/stable via `regr_slope` (linear regression)
- Anomaly detection — z-score per room (population stddev); z ≥ 3 → medium, z ≥ 5 → high
- Occupancy anomaly detection — room occupied during typically empty hours (occupancy_rate < 20%) → unusual_activity (medium)
- Spatial analysis — GeoPandas aggregates anomalies per building (lat/lon), writes to `spatial_insights` for the Power BI map visual
- dbt reporting layer — staging views + materialized marts (`anomaly_detail`, `pattern_detail`, `building_summary`) with source tests
- Observability — OTel counters per pipeline step, Airflow StatsD metrics, PostgreSQL metrics via postgres-exporter → Grafana Cloud

**Note:** the spatial analysis (`jobs/spatial.py`) is specific to project 2b. Project 2a exposes results via a REST API; Power BI can use the `rooms` table directly there. GeoPandas fits the Data Engineering stack of project 2b (Python jobs pipeline), not the AWS Lambda architecture of 2a.

## Database Schema (PostgreSQL)

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

**Table:** `patterns`
```sql
CREATE TABLE patterns (
    id           BIGSERIAL   PRIMARY KEY,
    job_id       TEXT        NOT NULL,
    entity_type  TEXT        NOT NULL,
    entity_id    TEXT        NOT NULL,
    pattern_type TEXT        NOT NULL,
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
    entity_type  TEXT        NOT NULL,
    entity_id    TEXT        NOT NULL,
    anomaly_type TEXT        NOT NULL,
    detected_at  TIMESTAMPTZ NOT NULL,
    severity     TEXT        NOT NULL,
    data         JSONB       NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Table:** `spatial_insights` *(geschreven door `jobs/spatial.py`)*
```sql
CREATE TABLE spatial_insights (
    id            BIGSERIAL        PRIMARY KEY,
    job_id        TEXT             NOT NULL,
    building_id   TEXT             NOT NULL,
    building_name TEXT             NOT NULL,
    lat           DOUBLE PRECISION NOT NULL,
    lon           DOUBLE PRECISION NOT NULL,
    anomaly_count INTEGER          NOT NULL,
    high_count    INTEGER          NOT NULL,
    medium_count  INTEGER          NOT NULL,
    dominant_type TEXT,
    period_start  TIMESTAMPTZ      NOT NULL,
    period_end    TIMESTAMPTZ      NOT NULL,
    created_at    TIMESTAMPTZ      NOT NULL DEFAULT NOW()
);
```

## dbt Reporting Layer

`dbt run` materializes staging views and marts directly in PostgreSQL — ready for Power BI DirectQuery.

### Models

**Staging** (views — no extra storage):

| Model | Source | Transformation |
|---|---|---|
| `stg_anomalies` | `anomalies` table | `entity_id` renamed to `room_id` |
| `stg_patterns` | `patterns` table | `entity_id` renamed to `room_id` |
| `stg_rooms` | `rooms` table | No transformation |

**Marts** (materialized tables — Power BI-ready):

**`anomaly_detail`** — anomalies joined with rooms, including time extractions:
```sql
room_id | building_id | building_name | lat | lon | anomaly_type | severity | detected_at | detected_hour | detected_dow
```

**`pattern_detail`** — patterns joined with rooms:
```sql
room_id | building_id | building_name | pattern_type | period_start | period_end
```

**`building_summary`** — aggregation per building across all jobs:
```sql
building_id | building_name | lat | lon | anomaly_count | high_count | medium_count | dominant_type | last_anomaly_at
```

### Source tests (`dbt test`)

| Test | Column |
|---|---|
| unique + not_null | `anomalies.id`, `rooms.room_id` |
| accepted_values | `anomalies.anomaly_type` → [temperature, unusual_activity] |
| accepted_values | `anomalies.severity` → [medium, high] |
| accepted_values | `patterns.pattern_type` → [occupancy_schedule, temperature_trend] |

### Difference from `spatial_insights`

| | `spatial_insights` | `building_summary` (dbt) |
|---|---|---|
| **Written by** | `jobs/spatial.py` (GeoPandas) | dbt mart |
| **Scope** | Per job (job_id present) | All jobs cumulated |
| **Purpose** | Power BI map visual (bubble per building per run) | Overview across all runs |

## Power BI Dashboard

### Temperature Trend per room — linear regression slope via PySpark regr_slope

![Power BI temperature trend](../../docs/screenshots/project2b-PySpark/project2b-powerbi-temperature-trend.png)

### Patterns Summary — occupancy schedule and temperature trend per room

![Power BI patterns summary](../../docs/screenshots/project2b-PySpark/project2b-powerbi-patterns-summary.png)

## Observability

**Architecture:** OTel Collector receives metrics from three sources and forwards them to Grafana Cloud.

```
Airflow (StatsD)  ──►┐
jobs/*.py (OTLP)  ──►│  OTel Collector  ──►  Grafana Cloud (Mimir + Loki)
postgres-exporter ──►┘
```

**Airflow StatsD** — DAG run duration, task success/failure, retry counts per task.

**Custom job metrics** (OTel counters via `jobs/metrics.py`):

| Metric | Job |
|---|---|
| `p2b.extract.records_scanned` | DynamoDB items read |
| `p2b.extract.records_written` | Records written to S3/raw |
| `p2b.transform.records_raw` | Raw records read |
| `p2b.transform.records_processed` | Valid records to S3/processed |
| `p2b.transform.records_dropped` | Filtered records (null, out-of-range) |
| `p2b.analyze.anomalies_detected` | Total anomalies per run |
| `p2b.analyze.patterns_detected` | Total patterns per run |
| `p2b.spatial.buildings_processed` | Buildings in spatial_insights |

**PostgreSQL metrics** — `postgres-exporter` container scrapes query latency, connections, table sizes via a Prometheus endpoint → OTel Collector.

`jobs/metrics.py` is a no-op if `OTEL_EXPORTER_OTLP_ENDPOINT` is not set — jobs simply run without metrics in the local dev environment.

## Installation & Usage

```bash
cd backend/project2b-behavior-analyzer

# Set up local database (PostgreSQL via Docker)
docker-compose -f docker/docker-compose.yml up -d postgres

# Run database migrations
python scripts/migrate.py

# Seed rooms with buildings and coordinates
python scripts/seed_rooms.py

# Manually start a job (requires .env with AWS + DB credentials)
spark-submit --master local[*] jobs/extract.py
spark-submit --master local[*] jobs/transform.py
spark-submit --master local[*] jobs/analyze.py
python jobs/spatial.py
```

See `.env.example` for the required environment variables.

## Testing

```bash
# Activate virtual environment
source .venv/bin/activate

# Unit tests
pytest tests/unit/

# Coverage report
pytest tests/unit/ --cov=jobs --cov=dags --cov-report=term-missing
```

### Coverage approach

`pragma: no cover` is used **only** on functions that require real infrastructure to run:

| Function | Reason |
|---|---|
| `scan_dynamodb` | Requires a real DynamoDB connection |
| `write_parquet` | Requires a real S3 connection |
| `read_raw`, `read_processed` | Requires a real S3 connection |
| `write_patterns`, `write_anomalies` | Requires real PostgreSQL + JDBC |
| `build_spark` | Requires a Spark cluster |

Pipeline orchestration (`main()` in all three jobs) has **no** `pragma: no cover` — it's tested via mocks.

Future extension: integration tests via LocalStack (S3 mock) + local PostgreSQL to also cover the I/O functions.
