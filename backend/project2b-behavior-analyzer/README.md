# Project 2b — Behavior Pattern Analyzer (Data Engineering stack)

## Beschrijving

ETL pipeline die sensor data uit project 1a (DynamoDB) extraheert, transformeert en analyseert via PySpark. Detecteert gedragspatronen en anomalieën per kamer en schrijft resultaten naar PostgreSQL. Gevisualiseerd in Power BI.

Zelfde analytisch doel als project 2a — bewust opnieuw geïmplementeerd met een Data Engineering stack om het contrast te tonen: AWS native (Lambda + Step Functions) vs. PySpark + Airflow.

## Stack

- **Processing:** PySpark 4.x (Spark SQL, window functions, `regr_slope`)
- **Orchestration:** Apache Airflow 2.x (DAG met BashOperators)
- **Storage:** AWS S3 (data lake — raw + processed Parquet), PostgreSQL (resultaten)
- **Visualization:** Power BI (direct connect op PostgreSQL)
- **IaC:** Terraform (S3 bucket + IAM)
- **CI/CD:** GitHub Actions (CI) + Jenkins (CD)
- **Testing:** pytest + PySpark in-process

## Data Lake Architecture

Drie lagen op S3 (Medallion architecture):

```
DynamoDB (prod-SensorEvents)
    │
    ▼  jobs/extract.py  (spark-submit)
S3/raw        ← Bronze: ruwe Parquet, gepartitioneerd per jaar/maand
    │
    ▼  jobs/transform.py  (spark-submit)
S3/processed  ← Silver: gevalideerd en opgeschoond Parquet
    │
    ▼  jobs/analyze.py  (spark-submit)
PostgreSQL    ← Gold: patronen + anomalieën (voor Power BI)
```

Idempotent: `partitionOverwriteMode=dynamic` — re-runnen overschrijft alleen de betreffende maandpartities.

## Design Decisions

**Bronze laag bevat genormaliseerd Parquet, niet ruwe JSON**

In een strikte Medallion architectuur zou Bronze de DynamoDB items bewaren als ruwe JSON — exact zoals de bron ze levert. Hier schrijft `extract.py` al als Parquet naar Bronze, na een lichte normalisatie van twee event formaten (project 2b seed format + project 1b API format) naar één unified schema.

Trade-off: Parquet is gecomprimeerd en efficiënt leesbaar door Spark. Ruwe JSON in Bronze zou volledige herverwerking toelaten bij een bug in de extractie — dat is hier niet mogelijk. Voor een portfolio met beperkte dataset is dit aanvaardbaar; in productie zou ik Bronze als ruwe JSON bewaren.

**Gold laag in PostgreSQL, niet op S3**

`analyze.py` schrijft patronen en anomalieën naar PostgreSQL via JDBC in plaats van naar S3 Gold. Reden: Power BI verbindt eenvoudiger met een SQL database dan met S3 + Athena. In een volledig AWS-native setup zou Gold als Parquet op S3 staan en Athena de query-laag vormen.

## Airflow DAG

`dags/behavior_pipeline.py` — wekelijks elke maandag om 02:00:

```
manage_partitions >> extract >> transform >> analyze
```

- `on_failure_callback` logt een `[ALERT]` na alle retries uitgeput
- `SPARK_MASTER` configureerbaar via env var (default: `local[*]`)

## Features

- Occupancy schedule detectie — gemiddelde bezettingsgraad per (kamer, dag, uur) via window aggregatie
- Temperature trend — stijgend/dalend/stabiel via `regr_slope` (lineaire regressie)
- Anomalie detectie — z-score per kamer (populatie stddev); z ≥ 3 → medium, z ≥ 5 → high

## Database Schema (PostgreSQL)

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

## Installatie & Gebruik

```bash
cd backend/project2b-behavior-analyzer

# Lokale database opzetten (PostgreSQL via Docker)
docker-compose -f docker/docker-compose.yml up -d postgres

# Database migraties uitvoeren
python scripts/migrate.py

# Handmatig een job starten (vereist .env met AWS + DB credentials)
spark-submit --master local[*] jobs/extract.py
spark-submit --master local[*] jobs/transform.py
spark-submit --master local[*] jobs/analyze.py
```

Zie `.env.example` voor de vereiste environment variabelen.

## Testing

```bash
# Virtual environment activeren
source .venv/bin/activate

# Unit tests
pytest tests/unit/

# Coverage rapport
pytest tests/unit/ --cov=jobs --cov=dags --cov-report=term-missing
```

### Coverage aanpak

`pragma: no cover` staat **alleen** op functies die echte infrastructuur vereisen om te draaien:

| Functie | Reden |
|---|---|
| `scan_dynamodb` | Vereist echte DynamoDB verbinding |
| `write_parquet` | Vereist echte S3 verbinding |
| `read_raw`, `read_processed` | Vereist echte S3 verbinding |
| `write_patterns`, `write_anomalies` | Vereist echte PostgreSQL + JDBC |
| `build_spark` | Vereist een Spark cluster |

Pipeline orchestratie (`main()` in alle drie jobs) heeft **geen** `pragma: no cover` — dat wordt getest via mocks.

Toekomstige uitbreiding: integratie tests via LocalStack (S3 mock) + lokale PostgreSQL om de I/O functies ook te dekken.
