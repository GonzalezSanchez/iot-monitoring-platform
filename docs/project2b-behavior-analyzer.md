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
| Tussenopslag | Aurora Serverless v2 | S3 Parquet (data lake) |
| Serving layer | Aurora Serverless v2 | PostgreSQL (self-hosted Docker) |
| Visualisatie | REST API | Power BI (DirectQuery op PostgreSQL) |
| CD | — | Jenkins (dev → staging → prod) |

## Tech Stack

- **Orkestratie:** Apache Airflow 2.x (Docker via officieel `apache/airflow` image)
- **Processing:** PySpark 4.x (Spark SQL voor patroon- en anomaliedetectie)
- **Data lake:** AWS S3 (`p2b-prod-sensor-events`) — raw en processed Parquet, gepartitioneerd op jaar/maand
- **Database:** PostgreSQL via Docker Compose op acer-server — serving layer voor Power BI (self-hosted, geen AWS kosten) + pgvector extensie
- **Visualisatie:** Power BI Desktop (DirectQuery op PostgreSQL)
- **Infra:** Terraform (S3 bucket + IAM)
- **CI:** GitHub Actions (ruff, mypy, pytest, terraform validate)
- **CD:** Jenkins (declaratief, lokaal via Docker — zie [docs/jenkins-cd-pipeline.md](jenkins-cd-pipeline.md))

## Architectuur

Data lake patroon met drie lagen: landing zone → staging → serving.

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
                    PostgreSQL (Docker, acer-server)    ← serving layer voor Power BI
                    ├── patterns         (occupancy_schedule + temperature_trend)
                    └── anomalies        (temperature z-score anomalies)
                              │
                              ▼
                    Power BI rapport (DirectQuery)
```

### Waarom S3 als tussenlaag?

Standaard data lake patroon — elke job leest en schrijft onafhankelijk:

| Laag | S3 pad | Inhoud |
|------|--------|--------|
| Landing zone | `s3a://p2b-prod-sensor-events/raw/` | Ruwe DynamoDB events als Parquet, gepartitioneerd op jaar/maand |
| Staging | `s3a://p2b-prod-sensor-events/processed/` | Gevalideerde, schoongemaakte events |
| Serving | PostgreSQL (`patterns` + `anomalies`) | Geaggregeerde resultaten voor Power BI |

Beide S3 lagen zijn idempotent via dynamic partition overwrite: re-run overschrijft alleen de getroffen maandpartities, niet de volledige dataset.

### Waarom PostgreSQL alleen aan het einde?

Power BI kan S3 Parquet niet rechtstreeks bevragen — het heeft een SQL endpoint nodig.
Alternatieven zoals Amazon Athena of Redshift brengen extra AWS kosten met zich mee.
PostgreSQL draait self-hosted op acer-server via Docker (altijd live, geen destroy cyclus)
en vermijdt zo RDS kosten van ~€15–20/maand. Alleen de uiteindelijke aggregaten
(`patterns` + `anomalies`) worden naar PostgreSQL geschreven — de bulkdata blijft in S3.

## PySpark Jobs

### Extract (`jobs/extract.py`)

- Scant DynamoDB tabel `prod-SensorEvents` (met paginering)
- Verwerkt twee event formats:
  - Seed format: `payload` JSON veld met alle sensors per event
  - Project 1b format: `sensor_type` + `value` per individueel event
- Schrijft als Parquet naar S3 landing zone, gepartitioneerd op jaar/maand
- Idempotent: dynamic partition overwrite — re-run overschrijft alleen de getroffen maandpartities

### Transform (`jobs/transform.py`)

- Leest Parquet van S3 landing zone (`raw/`)
- Filtert ongeldige sensorwaarden:
  - Temperatuur: null of buiten −10°C – 60°C → verwijderd
  - Vochtigheid: null of buiten 0–100% → verwijderd
- Hernoemt kolommen naar verwerkt schema (`temperature` → `temperature_c`, `humidity` → `humidity_pct`)
- Schrijft naar S3 processed layer (`processed/`), gepartitioneerd op jaar/maand
- Idempotent: dynamic partition overwrite

### Analyze (`jobs/analyze.py`)

- Leest verwerkte Parquet van S3 processed layer
- **Patroondetectie via Spark SQL:**
  - `occupancy_schedule`: gemiddelde bezetting per (kamer, dag van de week, uur) via `avg()` en window aggregatie
  - `temperature_trend`: regressiehelling via `regr_slope(temperature_c, unix_seconds)` — equivalent aan MLlib LinearRegression, efficiënter voor per-groepsberekening
- **Anomaliedetectie:**
  - Populatie-stddev per kamer via Spark window functions
  - Minimum 4 metingen per kamer vereist (statistisch minimum — zelfde als project 2a)
  - z-score ≥ 3 → severity `medium`; z-score ≥ 5 → severity `high`
- Schrijft **uitsluitend** naar PostgreSQL serving layer via JDBC:
  - `patterns` — occupancy_schedule + temperature_trend per kamer
  - `anomalies` — individuele temperatuurafwijkingen met z-score

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
    schedule="0 2 * * 1",          # elke maandag 02:00
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

PostgreSQL wordt uitsluitend gebruikt als serving layer — de bulkdata zit in S3 Parquet.
Alleen geaggregeerde resultaten worden naar de database geschreven.

Zelfde schema als Project 2a — opzettelijk, om portabiliteit te demonstreren.

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

**raw_sensor_data** (gepartitioneerde tabel, aangemaakt door `migrate.py`):
```sql
-- Maandelijks gepartitioneerd op ts — beheerd door manage_partitions.py
-- Geïnspireerd op fastapi-dbuploader/src/common/partitions.py
-- In de huidige pipeline dient S3 Parquet als de landing zone;
-- deze tabel is aanwezig voor compatibiliteit en eventuele uitbreidingen.
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

Maandelijkse partities voor `raw_sensor_data` worden beheerd door `scripts/manage_partitions.py`.
Airflow draait dit automatisch aan het begin van elke DAG run.

```bash
# Maak partities aan voor de komende 3 maanden
python scripts/manage_partitions.py --months-ahead 3

# Maak ook historische partities aan (nuttig bij eerste setup met bestaande data)
python scripts/manage_partitions.py --months-back 2 --months-ahead 3

# Dry run — print SQL zonder uit te voeren
python scripts/manage_partitions.py --months-ahead 3 --dry-run
```

## Pipeline Resultaten (eerste productierun, mei 2026)

| Stap | Resultaat |
|------|-----------|
| Extract (DynamoDB → S3/raw) | 12.744 events |
| Transform (S3/raw → S3/processed) | 12.715 events (29 verwijderd wegens ongeldige sensorwaarden) |
| Analyze — occupancy patterns | 5 kamerrijen (per kamer 1 schedule) |
| Analyze — temperature trends | 5 kamerrijen (per kamer 1 trend) |
| Analyze — anomalies | 22 afwijkingen gedetecteerd |

## Lokale Setup

Prerequisites:
- Docker Compose services draaien
- `.env` bestand aangemaakt (kopieer van `.env.example` en vul in)
- AWS credentials geconfigureerd (`aws sts get-caller-identity` moet werken)
- S3 bucket aangemaakt (`cd infrastructure && terraform apply`)

```bash
cd backend/project2b-behavior-analyzer

# 1. Start services (PostgreSQL)
docker compose -f docker/docker-compose.yml up -d

# 2. Maak database tabellen aan
python scripts/migrate.py

# 3. Maak partities aan voor historische + toekomstige maanden
python scripts/manage_partitions.py --months-back 2 --months-ahead 3

# 4. Seed testdata in DynamoDB (eenmalig — hergebruik project 2a script)
python ../project2a-behavior-analyzer/scripts/seed_dynamodb.py

# 5. Draai de pipeline
PACKAGES="org.apache.hadoop:hadoop-aws:3.4.2,com.amazonaws:aws-java-sdk-bundle:1.12.262,org.postgresql:postgresql:42.7.3"
S3A="com.amazonaws.auth.DefaultAWSCredentialsProviderChain"

spark-submit --packages $PACKAGES --conf spark.hadoop.fs.s3a.aws.credentials.provider=$S3A jobs/extract.py
spark-submit --packages $PACKAGES --conf spark.hadoop.fs.s3a.aws.credentials.provider=$S3A jobs/transform.py
spark-submit --packages $PACKAGES --conf spark.hadoop.fs.s3a.aws.credentials.provider=$S3A jobs/analyze.py
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

Huidig: **65 unit tests**, alle groen.

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
│   ├── extract.py               ← PySpark: DynamoDB → S3 raw Parquet
│   ├── transform.py             ← PySpark: S3 raw → S3 processed Parquet
│   └── analyze.py               ← PySpark: S3 processed → PostgreSQL (patronen + anomalieën)
├── infrastructure/
│   ├── s3.tf                    ← S3 bucket (p2b-prod-sensor-events)
│   ├── iam.tf                   ← IAM user voor Airflow worker (S3 + DynamoDB read)
│   ├── variables.tf
│   ├── outputs.tf
│   └── terraform.tfvars
├── scripts/
│   ├── migrate.py               ← DB schema aanmaken (patterns + anomalies)
│   ├── manage_partitions.py     ← maandelijkse partities aanmaken (--months-back + --months-ahead)
│   └── (geen seed script — hergebruik backend/project2a-behavior-analyzer/scripts/seed_dynamodb.py)
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
