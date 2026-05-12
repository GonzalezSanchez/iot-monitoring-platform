# Scripts

## Overview

| Script | Purpose | When to run |
|--------|---------|-------------|
| `migrate.py` | Creates/updates all PostgreSQL tables and indexes | Once after first setup, and after every schema change |
| `manage_partitions.py` | Creates monthly partitions for `raw_sensor_data` | Before first extract run, then automatically by Airflow DAG |

## Testdata

Project 2b leest van dezelfde DynamoDB tabel als project 2a (`prod-SensorEvents`).

Gebruik het seed script van project 2a om testdata te genereren:

```bash
python backend/project2a-behavior-analyzer/scripts/seed_dynamodb.py
```

Dit genereert 30 dagen aan sensor events voor 5 kamers. Zie project 2a scripts/README.md voor alle opties.

## Architectuuroverzicht

Data lake patroon met drie lagen:

| Laag | Opslag | PySpark job |
|------|--------|-------------|
| Landing zone | `s3a://p2b-prod-sensor-events/raw/` | `extract.py` (DynamoDB → S3 Parquet) |
| Staging | `s3a://p2b-prod-sensor-events/processed/` | `transform.py` (valideren, schoonmaken) |
| Serving | PostgreSQL (`patterns` + `anomalies`) | `analyze.py` (patronen + anomalieën → Power BI) |

PostgreSQL draait self-hosted op acer-server via Docker. Dit vermijdt AWS RDS kosten (~€15–20/maand)
en maakt directe Power BI verbinding mogelijk zonder extra AWS services (Athena, Redshift).

## Setup (eerste keer)

Prerequisites:
- Docker Compose services draaien: `docker compose -f docker/docker-compose.yml up -d`
- `.env` bestand aangemaakt (kopieer van `.env.example` en vul in)
- AWS credentials geconfigureerd (`aws sts get-caller-identity` moet werken)
- S3 bucket aangemaakt: `cd infrastructure && terraform apply`

```bash
cd backend/project2b-behavior-analyzer

# Activeer de virtual environment
source .venv/bin/activate

# 1. Start services (PostgreSQL)
docker compose -f docker/docker-compose.yml up -d

# 2. Maak database tabellen aan
python scripts/migrate.py

# 3. Maak partities aan voor historische + toekomstige maanden
python scripts/manage_partitions.py --months-back 2 --months-ahead 3

# 4. Seed testdata in DynamoDB (eenmalig — hergebruik project 2a script)
python ../project2a-behavior-analyzer/scripts/seed_dynamodb.py

# 5. Draai de pipeline
#    Benodigde JAR pakketten:
#      - hadoop-aws + aws-java-sdk-bundle: S3A connector (s3a:// schema voor Spark)
#      - postgresql JDBC driver: voor JDBC write naar PostgreSQL (alleen analyze.py)
PACKAGES="org.apache.hadoop:hadoop-aws:3.4.2,com.amazonaws:aws-java-sdk-bundle:1.12.262,org.postgresql:postgresql:42.7.3"
S3A="com.amazonaws.auth.DefaultAWSCredentialsProviderChain"

spark-submit --packages $PACKAGES --conf spark.hadoop.fs.s3a.aws.credentials.provider=$S3A jobs/extract.py
spark-submit --packages $PACKAGES --conf spark.hadoop.fs.s3a.aws.credentials.provider=$S3A jobs/transform.py
spark-submit --packages $PACKAGES --conf spark.hadoop.fs.s3a.aws.credentials.provider=$S3A jobs/analyze.py
```

## migrate.py

Maakt de serving layer tabellen aan in PostgreSQL. Idempotent — veilig om meerdere keren te draaien.

Aangemaakt:
- `patterns` — geaggregeerde patroonresultaten (occupancy_schedule, temperature_trend) — actief geschreven door `analyze.py`
- `anomalies` — gedetecteerde temperatuurafwijkingen — actief geschreven door `analyze.py`
- `raw_sensor_data` — gepartitioneerde tabel (S3 Parquet is de primaire opslag; deze tabel is aanwezig voor uitbreidingen)

```bash
python scripts/migrate.py
```

## manage_partitions.py

Maakt maandelijkse partities aan voor de `raw_sensor_data` tabel. Airflow draait dit automatisch
aan het begin van elke DAG run. Handmatig draaien is alleen nodig voor de eerste setup.

```bash
# Maak partities voor de komende 3 maanden
python scripts/manage_partitions.py --months-ahead 3

# Maak ook historische partities aan (voor bestaande of gebackfillde data)
python scripts/manage_partitions.py --months-back 2 --months-ahead 3

# Dry run — print SQL zonder uit te voeren
python scripts/manage_partitions.py --months-ahead 3 --dry-run
```

## Lokale setup vs. acer-server

- **Lokaal:** Docker Compose op je eigen machine — voor development en testen
- **acer-server:** Docker Compose op `ags@acer.gonzalezsanchez.dev` — permanente deployment
  - Deploy: `git pull && docker compose -f docker/docker-compose.yml up -d`
  - Nooit committen op de server — alleen `git pull`
