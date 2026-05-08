# Project 2b: Behavior Pattern Analyzer (Data Engineering Stack)

## Beschrijving

Dezelfde analytics als Project 2a — gedragspatronen en anomalieën detecteren uit
sensordata — maar nu geïmplementeerd met een data engineering stack. Een bewuste
herhaling om te demonstreren dat dezelfde businesslogica met andere tools oplosbaar is.

**Vergelijking met Project 2a:**

| Aspect | Project 2a (AWS native) | Project 2b (Data Engineering) |
|--------|------------------------|-------------------------------|
| Orkestratie | AWS Step Functions | Apache Airflow |
| Processing | Python (pandas) | PySpark (gedistribueerd) |
| Infra | Terraform + Aurora Serverless v2 | Terraform + S3 + IAM (PostgreSQL via Docker op server) |
| Visualisatie | REST API | Power BI rapport |
| AI interface | — | — (zie Project 4) |
| CD | — | Jenkins (dev → staging → prod) |

## Tech Stack

- **Orkestratie:** Apache Airflow 2.x (Docker via officieel `apache/airflow` image)
- **Processing:** PySpark 3.x (Spark SQL + MLlib voor patroondetectie)
- **Database:** PostgreSQL via Docker Compose (lokaal + acer-server — altijd live, geen AWS kosten) + pgvector extensie
- **Opslag:** S3 (ruwe sensor events als Parquet bestanden)
- **Visualisatie:** Power BI Desktop (DirectQuery op PostgreSQL)
- **LLM / RAG:** OpenAI API (of Ollama lokaal) + pgvector voor semantisch zoeken over patronen en anomalieën
- **Infra:** Terraform
- **CI:** GitHub Actions (ruff, mypy, pytest, terraform validate)
- **CD:** Jenkins (declaratief, lokaal via Docker — zie [docs/jenkins-cd-pipeline.md](jenkins-cd-pipeline.md))

## Architectuur

```
DynamoDB (prod-SensorEvents)
        │
        ▼ (via Airflow DAG: @weekly)
┌────────────────────────────────────────────────────┐
│  Airflow DAG: behavior_pipeline                    │
│                                                    │
│  extract_task → transform_task → analyze_task      │
└────────────────────────────────────────────────────┘
        │              │              │
        ▼              ▼              ▼
  PySpark Job:   PySpark Job:   PySpark Job:
  Extract        Transform      Analyze
  (DynamoDB →    (normalize,    (Spark SQL +
   S3 Parquet     validate)      MLlib)
   + JDBC)
        │
        ▼
  PostgreSQL (Docker)
  ├── raw_sensor_data
  ├── processed_sensor_data
  ├── patterns
  └── anomalies
        │
        ▼
  Power BI rapport
  (DirectQuery)
```

## Database Schema (PostgreSQL)

Zelfde schema als Project 2a — opzettelijk, om portabiliteit te demonstreren.

De maandelijkse partitionering van `raw_sensor_data` is geïnspireerd op het
[fastapi-dbuploader](https://gitlab.com/dmorel69/fastapi-dbuploader) project
(gebruikt met toestemming — zie LinkedIn conversatie april 2026).

**raw_sensor_data** (maandelijks gepartitioneerd op `ts`):
```sql
-- Partitioned table — inspired by https://gitlab.com/dmorel69/fastapi-dbuploader
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

-- Monthly partitions created automatically by scripts/manage_partitions.py
-- Example: raw_sensor_data_2026_01, raw_sensor_data_2026_02, ...
CREATE INDEX IF NOT EXISTS idx_raw_sensor_data_room_id ON raw_sensor_data (room_id);
CREATE INDEX IF NOT EXISTS idx_raw_sensor_data_event_id ON raw_sensor_data (event_id);
```

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

## Partition Management

Maandelijkse partities voor `raw_sensor_data` worden beheerd door `scripts/manage_partitions.py`.
Dit script is geïnspireerd op `fastapi-dbuploader/src/common/partitions.py`
(gebruikt met toestemming — zie LinkedIn conversatie april 2026).

```bash
# Maak partities aan voor de komende 3 maanden
python scripts/manage_partitions.py --months-ahead 3

# Dry run — print SQL zonder uit te voeren
python scripts/manage_partitions.py --months-ahead 3 --dry-run
```

Het script draait ook als Airflow task aan het begin van elke DAG run zodat
partities altijd bestaan voor de huidige en volgende maand.

## PySpark Jobs

### Extract (`jobs/extract.py`)
- Leest sensor events van DynamoDB (`prod-SensorEvents`)
- Schrijft ruwe events als Parquet naar S3 (data lake archief)
- Laadt rijen naar `raw_sensor_data` via JDBC (PostgreSQL)
- Idempotent: `INSERT ... ON CONFLICT DO NOTHING` via Spark JDBC mode `"ignore"`

### Transform (`jobs/transform.py`)
- Leest `raw_sensor_data` waar `processed = FALSE`
- Filtert ongeldige sensorwaarden (null, buiten bereik)
- Normaliseert eenheden (Fahrenheit → Celsius, etc.)
- Markeert rijen als `processed = TRUE`

### Analyze (`jobs/analyze.py`)
- **Patroondetectie via Spark SQL:**
  - `occupancy_schedule`: window functions per uur per dag → mediaan bezetting
  - `temperature_trend`: lineaire regressie via `pyspark.ml.regression.LinearRegression`
- **Anomaliedetectie:**
  - z-score berekening: `(value - mean) / stddev` via Spark SQL aggregates
  - Minimum 4 metingen per kamer vereist (zelfde als project 2a — minder is statistisch onbetrouwbaar)
  - z-score ≥ 3 → severity `medium`
  - z-score ≥ 5 → severity `high`

## Airflow DAG

```python
# dags/behavior_pipeline.py
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

with DAG(
    dag_id="behavior_pipeline",
    schedule="0 2 * * 1",          # elke maandag 02:00
    start_date=datetime(2026, 1, 1),
    catchup=False,
    params={"days_back": 7},
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
) as dag:
    extract  = BashOperator(task_id="extract",  bash_command="spark-submit jobs/extract.py")
    transform= BashOperator(task_id="transform",bash_command="spark-submit jobs/transform.py")
    analyze  = BashOperator(task_id="analyze",  bash_command="spark-submit jobs/analyze.py")

    extract >> transform >> analyze
```

## Observability — OpenTelemetry + Grafana Cloud

Zelfde OTel Collector laag als project 1b — alleen de backend wisselt van Datadog naar
Grafana Cloud. Stack blijft altijd live (gratis tier, geen trial, geen destroy cyclus).

**Stack:**
```
Airflow + PostgreSQL + Spark
        ↓
OTel Collector (vendor-neutraal — zelfde aanpak als project 1b)
        ↓
Grafana Cloud
  ├── Mimir   (metrics)
  ├── Loki    (logs)
  └── Tempo   (traces)
```

**Wat wordt gemonitord:**
- **Airflow** — DAG run durations, task success/failure rates
- **PostgreSQL** — query latency, connections, disk I/O
- **Spark jobs** — job duration via Airflow task metrics
- **Infrastructure** — Docker container CPU/memory

**Aanpak (altijd live — zelfde filosofie als project 1a/1b):**
1. OTel Collector toevoegen aan `docker-compose.yml` naast de bestaande stack
2. Grafana Cloud free tier (hergebruik account van project 1b migratie)
3. Dashboards configureren voor Airflow + PostgreSQL
4. DAG draaien met testdata → metrics zichtbaar in Grafana
5. Screenshots opslaan in `docs/screenshots/`
6. Stack blijft live — gratis tier, geen doorlopende kosten

> RAG interface (LLM + pgvector) is onderdeel van **Project 4**, niet 2b.

---

## Power BI Rapport

- **Verbinding:** DirectQuery op PostgreSQL (`patterns` + `anomalies` tabellen)
- **Pagina's:**
  - Overzicht — patroon frequentie per kamer per week (bar chart)
  - Anomalieën — severity heatmap per kamer (matrix visualisatie)
  - Temperatuurtrend — lijndiagram met confidence band
- **Bestand:** `reports/behavior_analyzer.pbix` (gitignored — te groot voor Git)
- **Screenshot:** opgenomen in README voor portfolio presentatie

## Lokale Setup

```bash
cd backend/project2b-behavior-analyzer

# 1. Alle services starten (Airflow + PostgreSQL)
docker compose -f docker/docker-compose.yml up -d

# 2. DB migratie draaien
python scripts/migrate.py

# 3. Airflow bereikbaar op http://localhost:8080

# 4. DAG manueel triggeren
airflow dags trigger behavior_pipeline --conf '{"days_back": 7}'

# 6. Of PySpark job direct draaien (zonder Airflow)
spark-submit --master local[*] jobs/extract.py
spark-submit --master local[*] jobs/transform.py
spark-submit --master local[*] jobs/analyze.py
```

## Testing

```bash
# Unit tests (geen echte DB of Spark vereist)
pytest tests/unit/ -v --cov=jobs --cov=dags --cov-fail-under=80

# Integratie tests (vereist Docker services)
docker compose -f docker/docker-compose.yml up -d
pytest tests/integration/ -v --no-cov

# Linting + type checking
ruff check jobs/ dags/ scripts/
mypy jobs/ dags/
```

## CI/CD

- **CI:** GitHub Actions — ruff, mypy, pytest unit, terraform validate (bij elke push)
- **CD:** Jenkins declaratieve pipeline — packaging, terraform apply, environment promotie
  - Dev → staging: handmatige approval in Jenkins UI
  - Staging → prod: handmatige approval + second sign-off
  - Zie [docs/jenkins-cd-pipeline.md](jenkins-cd-pipeline.md) voor Jenkins setup

## Directory Structuur

```
backend/project2b-behavior-analyzer/
├── dags/
│   └── behavior_pipeline.py     ← Airflow DAG definitie
├── jobs/
│   ├── extract.py               ← PySpark: S3 Parquet → PostgreSQL
│   ├── transform.py             ← PySpark: normalize + validate
│   └── analyze.py               ← PySpark: patronen + anomalieën
├── infrastructure/
│   ├── s3.tf                    ← S3 bucket (ruwe sensor Parquet data)
│   ├── iam.tf                   ← IAM user voor Airflow worker (S3 + DynamoDB read)
│   ├── variables.tf
│   └── outputs.tf
├── scripts/
│   ├── migrate.py               ← DB schema aanmaken
│   ├── manage_partitions.py     ← maandelijkse partities aanmaken (geïnspireerd op fastapi-dbuploader)
│   └── seed_data.py             ← testdata seeden in DynamoDB (hergebruikt logica van project 2a)
├── rag/
│   └── bot.py                   ← RAG query interface (pgvector + LLM)
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
│   └── docker-compose.yml       ← Airflow + PostgreSQL
├── Jenkinsfile                  ← CD pipeline
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── README.md
```
