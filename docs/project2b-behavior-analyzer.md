# Project 2b: Behavior Pattern Analyzer (Data Engineering Stack)

**LinkedIn post:** [Same analytics goal. Completely different stack.](https://www.linkedin.com/posts/gonzalezsanchez_dataengineering-apacheairflow-pyspark-ugcPost-7460192378834890752-nb33)

## Description

The same analytics as Project 2a — detecting behavior patterns and anomalies from
sensor data — but now implemented with a data engineering stack. A deliberate
repetition to demonstrate that the same business logic can be solved with different tools.

**Comparison with Project 2a:**

| Aspect | Project 2a (AWS native) | Project 2b (Data Engineering) |
|--------|------------------------|-------------------------------|
| Orchestration | AWS Step Functions | Apache Airflow |
| Processing | Python (pandas) | PySpark (distributed) |
| Intermediate storage | Aurora Serverless v2 | S3 Parquet (data lake) |
| Serving layer | Aurora Serverless v2 | PostgreSQL (self-hosted Docker) |
| Visualization | REST API | Power BI (DirectQuery on PostgreSQL) |
| CD | — | Jenkins (dev → staging → prod) |

## Tech Stack

- **Orchestration:** Apache Airflow 2.x (Docker via official `apache/airflow` image)
- **Processing:** PySpark 4.x (Spark SQL for pattern and anomaly detection)
- **Data lake:** AWS S3 (`p2b-prod-sensor-events`) — raw and processed Parquet, partitioned by year/month
- **Database:** PostgreSQL via Docker Compose on acer-server — serving layer for Power BI (self-hosted, no AWS costs) + pgvector extension
- **Visualization:** Power BI Desktop (DirectQuery on PostgreSQL)
- **Infra:** Terraform (S3 bucket + IAM)
- **CI:** GitHub Actions (ruff, mypy, pytest, terraform validate)
- **CD:** Jenkins (declarative, local via Docker — see [docs/jenkins-cd-pipeline.md](jenkins-cd-pipeline.md))

## Architecture

Data lake pattern with three layers: landing zone → staging → serving.

```
DynamoDB (prod-SensorEvents)
        │
        ▼ (via Airflow DAG: @weekly)
┌─────────────────────────────────────────────────────────────────────────┐
│  Airflow DAG: behavior_pipeline                                         │
│                                                                         │
│  manage_partitions → extract_task → transform_task → analyze_task       │
└─────────────────────────────────────────────────────────────────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
  PySpark:             PySpark:             PySpark:
  Extract              Transform            Analyze
  (DynamoDB →          (S3/raw →            (S3/processed →
   S3/raw Parquet)      S3/processed)        PostgreSQL)
                                                  │
                              ┌───────────────────┘
                              ▼
                    PostgreSQL (Docker, acer-server)    ← serving layer for Power BI
                    ├── patterns         (occupancy_schedule + temperature_trend)
                    └── anomalies        (temperature z-score anomalies)
                              │
                              ▼
                    Power BI report (DirectQuery)
```

### Why S3 as an intermediate layer?

Standard data lake pattern — each job reads and writes independently:

| Layer | S3 path | Content |
|------|--------|--------|
| Landing zone | `s3a://p2b-prod-sensor-events/raw/` | Raw DynamoDB events as Parquet, partitioned by year/month |
| Staging | `s3a://p2b-prod-sensor-events/processed/` | Validated, cleaned events |
| Serving | PostgreSQL (`patterns` + `anomalies`) | Aggregated results for Power BI |

Both S3 layers are idempotent via dynamic partition overwrite: a re-run only overwrites the affected month partitions, not the full dataset.

### Why PostgreSQL only at the end?

Power BI can't query S3 Parquet directly — it needs a SQL endpoint.
Alternatives like Amazon Athena or Redshift bring extra AWS costs.
PostgreSQL runs self-hosted on acer-server via Docker (always live, no destroy cycle)
and thereby avoids RDS costs of ~€15–20/month. Only the final aggregates
(`patterns` + `anomalies`) are written to PostgreSQL — the bulk data stays in S3.

## PySpark Jobs

### Extract (`jobs/extract.py`)

- Scans DynamoDB table `prod-SensorEvents` (with pagination)
- Handles two event formats:
  - Seed format: `payload` JSON field with all sensors per event
  - Project 1b format: `sensor_type` + `value` per individual event
- Writes as Parquet to the S3 landing zone, partitioned by year/month
- Idempotent: dynamic partition overwrite — a re-run only overwrites the affected month partitions

### Transform (`jobs/transform.py`)

- Reads Parquet from the S3 landing zone (`raw/`)
- Filters invalid sensor values:
  - Temperature: null or outside −10°C – 60°C → removed
  - Humidity: null or outside 0–100% → removed
- Renames columns to the processed schema (`temperature` → `temperature_c`, `humidity` → `humidity_pct`)
- Writes to the S3 processed layer (`processed/`), partitioned by year/month
- Idempotent: dynamic partition overwrite

### Analyze (`jobs/analyze.py`)

- Reads processed Parquet from the S3 processed layer
- **Pattern detection via Spark SQL:**
  - `occupancy_schedule`: average occupancy per (room, day of week, hour) via `avg()` and window aggregation
  - `temperature_trend`: regression slope via `regr_slope(temperature_c, unix_seconds)` — equivalent to MLlib LinearRegression, more efficient for per-group computation
- **Anomaly detection:**
  - Population stddev per room via Spark window functions
  - Minimum 4 measurements per room required (statistical minimum — same as project 2a)
  - z-score ≥ 3 → severity `medium`; z-score ≥ 5 → severity `high`
- Writes **exclusively** to the PostgreSQL serving layer via JDBC:
  - `patterns` — occupancy_schedule + temperature_trend per room
  - `anomalies` — individual temperature deviations with z-score

## Airflow DAG

```python
# dags/behavior_pipeline.py
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

PACKAGES = (
    "org.apache.hadoop:hadoop-aws:3.4.2,"
    "com.amazonaws:aws-java-sdk-bundle:1.12.262,"
    "org.postgresql:postgresql:42.7.3"
)
S3A_PROVIDER = "com.amazonaws.auth.DefaultAWSCredentialsProviderChain"
SUBMIT = f"spark-submit --packages {PACKAGES} --conf spark.hadoop.fs.s3a.aws.credentials.provider={S3A_PROVIDER}"

with DAG(
    dag_id="behavior_pipeline",
    schedule="0 2 * * 1",          # every Monday 02:00
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
) as dag:
    partitions = BashOperator(task_id="manage_partitions", bash_command="python scripts/manage_partitions.py --months-ahead 2")
    extract    = BashOperator(task_id="extract",    bash_command=f"{SUBMIT} jobs/extract.py")
    transform  = BashOperator(task_id="transform",  bash_command=f"{SUBMIT} jobs/transform.py")
    analyze    = BashOperator(task_id="analyze",    bash_command=f"{SUBMIT} jobs/analyze.py")

    partitions >> extract >> transform >> analyze
```

## Database Schema (PostgreSQL)

PostgreSQL is used exclusively as a serving layer — the bulk data lives in S3 Parquet.
Only aggregated results are written to the database.

Same schema as Project 2a — deliberately, to demonstrate portability.

**patterns:**
```sql
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
CREATE INDEX idx_patterns_entity ON patterns (entity_type, entity_id);
CREATE INDEX idx_patterns_job_id ON patterns (job_id);
```

**anomalies:**
```sql
CREATE TABLE anomalies (
    id            BIGSERIAL     PRIMARY KEY,
    job_id        TEXT          NOT NULL,
    entity_type   TEXT          NOT NULL,
    entity_id     TEXT          NOT NULL,
    anomaly_type  TEXT          NOT NULL,
    detected_at   TIMESTAMPTZ   NOT NULL,
    severity      TEXT          NOT NULL,
    data          JSONB         NOT NULL,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_anomalies_entity ON anomalies (entity_type, entity_id);
CREATE INDEX idx_anomalies_job_id ON anomalies (job_id);
```

**raw_sensor_data** (partitioned table, created by `migrate.py`):
```sql
-- Partitioned monthly on ts — managed by manage_partitions.py
-- Inspired by fastapi-dbuploader/src/common/partitions.py
-- In the current pipeline, S3 Parquet serves as the landing zone;
-- this table is present for compatibility and possible future extensions.
CREATE TABLE IF NOT EXISTS raw_sensor_data (
    id            BIGSERIAL,
    event_id      TEXT          NOT NULL,
    device_id     TEXT          NOT NULL,
    room_id       TEXT          NOT NULL,
    ts            TIMESTAMPTZ   NOT NULL,
    temperature   DOUBLE PRECISION,
    humidity      DOUBLE PRECISION,
    motion        BOOLEAN,
    occupancy     BOOLEAN,
    raw_payload   JSONB         NOT NULL,
    ingested_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, ts)
) PARTITION BY RANGE (ts);

CREATE INDEX IF NOT EXISTS idx_raw_sensor_data_room_id ON raw_sensor_data (room_id);
CREATE INDEX IF NOT EXISTS idx_raw_sensor_data_event_id ON raw_sensor_data (event_id);
```

## Partition Management

Monthly partitions for `raw_sensor_data` are managed by `scripts/manage_partitions.py`.
Airflow runs this automatically at the start of every DAG run.

```bash
# Create partitions for the next 3 months
python scripts/manage_partitions.py --months-ahead 3

# Also create historical partitions (useful for first setup with existing data)
python scripts/manage_partitions.py --months-back 2 --months-ahead 3

# Dry run — print SQL without executing
python scripts/manage_partitions.py --months-ahead 3 --dry-run
```

## Pipeline Results (first production run, May 2026)

| Step | Result |
|------|-----------|
| Extract (DynamoDB → S3/raw) | 12,744 events |
| Transform (S3/raw → S3/processed) | 12,715 events (29 removed due to invalid sensor values) |
| Analyze — occupancy patterns | 5 room rows (1 schedule per room) |
| Analyze — temperature trends | 5 room rows (1 trend per room) |
| Analyze — anomalies | 22 anomalies detected |

## Local Setup

Prerequisites:
- Docker Compose services running
- `.env` file created (copy from `.env.example` and fill in)
- AWS credentials configured (`aws sts get-caller-identity` must work)
- S3 bucket created (`cd infrastructure && terraform apply`)

```bash
cd backend/project2b-behavior-analyzer

# 1. Start services (PostgreSQL)
docker compose -f docker/docker-compose.yml up -d

# 2. Create database tables
python scripts/migrate.py

# 3. Create partitions for historical + future months
python scripts/manage_partitions.py --months-back 2 --months-ahead 3

# 4. Seed test data into DynamoDB (one-off — reuses project 2a script)
python ../project2a-behavior-analyzer/scripts/seed_dynamodb.py

# 5. Run the pipeline
PACKAGES="org.apache.hadoop:hadoop-aws:3.4.2,com.amazonaws:aws-java-sdk-bundle:1.12.262,org.postgresql:postgresql:42.7.3"
S3A="com.amazonaws.auth.DefaultAWSCredentialsProviderChain"

spark-submit --packages $PACKAGES --conf spark.hadoop.fs.s3a.aws.credentials.provider=$S3A jobs/extract.py
spark-submit --packages $PACKAGES --conf spark.hadoop.fs.s3a.aws.credentials.provider=$S3A jobs/transform.py
spark-submit --packages $PACKAGES --conf spark.hadoop.fs.s3a.aws.credentials.provider=$S3A jobs/analyze.py
```

## Testing

```bash
# Unit tests (no real DB or Spark required)
pytest tests/unit/ -v --cov=jobs --cov=dags --cov-fail-under=80

# Integration tests (requires Docker services)
docker compose -f docker/docker-compose.yml up -d
pytest tests/integration/ -v --no-cov

# Linting + type checking
ruff check jobs/ dags/ scripts/
mypy jobs/ dags/
```

Current: **65 unit tests**, all green.

## Observability — OpenTelemetry + Grafana Cloud

Same OTel Collector layer as project 1b — only the backend switches from Datadog to
Grafana Cloud. The stack stays live at all times (free tier, no trial, no destroy cycle).

**Stack:**
```
Airflow + PostgreSQL + Spark
        ↓
OTel Collector (vendor-neutral — same approach as project 1b)
        ↓
Grafana Cloud
  ├── Mimir   (metrics)
  ├── Loki    (logs)
  └── Tempo   (traces)
```

**What gets monitored:**
- **Airflow** — DAG run durations, task success/failure rates
- **PostgreSQL** — query latency, connections, disk I/O
- **Spark jobs** — job duration via Airflow task metrics
- **Infrastructure** — Docker container CPU/memory

> The RAG interface (LLM + pgvector) is part of **Project 4**, not 2b.

---

## Future extensions
- Add integration tests (LocalStack + PostgreSQL) — unit tests cover pipeline logic, I/O functions not yet
- Include test coverage percentage in README (consistent with project 2a)
- Add Grafana Cloud screenshots (Mimir/Loki/Tempo dashboard)
- Short operations section: manual DAG trigger, pipeline recovery after a failed step, Jenkins rollback

## Power BI Report

- **Connection:** DirectQuery on PostgreSQL (`patterns` + `anomalies` tables)
- **Pages:**
  - Overview — pattern frequency per room per week (bar chart)
  - Anomalies — severity heatmap per room (matrix visualization)
  - Temperature trend — line chart with confidence band
- **File:** `reports/behavior_analyzer.pbix` (gitignored — too large for Git)
- **Screenshot:** included in README for portfolio presentation

## CI/CD

- **CI:** GitHub Actions — ruff, mypy, pytest unit, terraform validate (on every push)
- **CD:** Jenkins declarative pipeline — packaging, terraform apply, environment promotion
  - Dev → staging: manual approval in Jenkins UI
  - Staging → prod: manual approval + second sign-off
  - See [docs/jenkins-cd-pipeline.md](jenkins-cd-pipeline.md) for Jenkins setup

## Directory Structure

```
backend/project2b-behavior-analyzer/
├── dags/
│   └── behavior_pipeline.py     ← Airflow DAG definition
├── jobs/
│   ├── extract.py               ← PySpark: DynamoDB → S3 raw Parquet
│   ├── transform.py             ← PySpark: S3 raw → S3 processed Parquet
│   └── analyze.py               ← PySpark: S3 processed → PostgreSQL (patterns + anomalies)
├── infrastructure/
│   ├── s3.tf                    ← S3 bucket (p2b-prod-sensor-events)
│   ├── iam.tf                   ← IAM user for Airflow worker (S3 + DynamoDB read)
│   ├── variables.tf
│   ├── outputs.tf
│   └── terraform.tfvars
├── scripts/
│   ├── migrate.py               ← create DB schema (patterns + anomalies)
│   ├── manage_partitions.py     ← create monthly partitions (--months-back + --months-ahead)
│   └── (no seed script — reuses backend/project2a-behavior-analyzer/scripts/seed_dynamodb.py)
├── tests/
│   ├── unit/
│   │   ├── test_extract.py
│   │   ├── test_transform.py
│   │   ├── test_analyze.py
│   │   └── test_dag.py
│   └── integration/
│       └── test_pipeline.py
├── reports/                     ← Power BI .pbix (gitignored)
├── docker/
│   └── docker-compose.yml       ← PostgreSQL (pgvector/pgvector:pg16)
├── Jenkinsfile                  ← CD pipeline
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── README.md
```
