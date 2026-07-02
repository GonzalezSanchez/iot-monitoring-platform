# Scripts

## Overview

| Script | Purpose | When to run |
|--------|---------|-------------|
| `migrate.py` | Creates/updates all PostgreSQL tables and indexes | Once after first setup, and after every schema change |
| `manage_partitions.py` | Creates monthly partitions for `raw_sensor_data` | Before first extract run, then automatically by Airflow DAG |
| `seed_rooms.py` | Seeds 3 rooms with building names and coordinates | Once after migrate.py — required for spatial analysis |

## Test Data

Project 2b reads from the same DynamoDB table as project 2a (`prod-SensorEvents`).

Use the project 2a seed script to generate test data:

```bash
python backend/project2a-behavior-analyzer/scripts/seed_dynamodb.py
```

This generates 30 days of sensor events for 5 rooms. See project 2a scripts/README.md for all options.

## Architecture Overview

Data lake pattern with three layers:

| Layer | Storage | Job |
|------|--------|-----|
| Landing zone | `s3a://p2b-prod-sensor-events/raw/` | `extract.py` (DynamoDB → S3 Parquet) |
| Staging | `s3a://p2b-prod-sensor-events/processed/` | `transform.py` (validate, clean) |
| Serving | PostgreSQL (`patterns` + `anomalies`) | `analyze.py` (patterns + anomalies → Power BI) |
| Spatial | PostgreSQL (`spatial_insights`) | `spatial.py` (GeoPandas — anomalies per building → Power BI map) |

PostgreSQL runs self-hosted on acer-server via Docker. This avoids AWS RDS costs (~€15–20/month)
and enables a direct Power BI connection without extra AWS services (Athena, Redshift).

## Setup (first time)

Prerequisites:
- `.env` file created (copy from `.env.example` and fill in)
- AWS credentials filled in `.env` (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- S3 bucket created: `cd infrastructure && terraform apply`

> **Important:** always pass `--env-file .env` to `docker compose`. The compose file lives in
> `docker/` but `.env` lives in the project root — otherwise Docker Compose won't find it.

```bash
cd backend/project2b-behavior-analyzer

# Activate the virtual environment
source .venv/bin/activate

# 1. Start services (PostgreSQL + Airflow)
docker compose -f docker/docker-compose.yml --env-file .env up -d

# 2. Create database tables
python scripts/migrate.py

# 3. Create partitions for historical + future months
python scripts/manage_partitions.py --months-back 2 --months-ahead 3

# 4. Seed test data into DynamoDB (one-off — reuses project 2a script)
python ../project2a-behavior-analyzer/scripts/seed_dynamodb.py

# 5. Seed rooms with buildings and coordinates
python scripts/seed_rooms.py

# 6. Run the pipeline
#    Required JAR packages:
#      - hadoop-aws + aws-java-sdk-bundle: S3A connector (s3a:// schema for Spark)
#      - postgresql JDBC driver: for JDBC write to PostgreSQL (analyze.py only)
PACKAGES="org.apache.hadoop:hadoop-aws:3.4.2,com.amazonaws:aws-java-sdk-bundle:1.12.262,org.postgresql:postgresql:42.7.3"
S3A="com.amazonaws.auth.DefaultAWSCredentialsProviderChain"

spark-submit --packages $PACKAGES --conf spark.hadoop.fs.s3a.aws.credentials.provider=$S3A jobs/extract.py
spark-submit --packages $PACKAGES --conf spark.hadoop.fs.s3a.aws.credentials.provider=$S3A jobs/transform.py
spark-submit --packages $PACKAGES --conf spark.hadoop.fs.s3a.aws.credentials.provider=$S3A jobs/analyze.py
```

## migrate.py

Creates the serving layer tables in PostgreSQL. Idempotent — safe to run multiple times.

Created:
- `rooms` — static room/building registry with coordinates — populated via `seed_rooms.py`
- `patterns` — aggregated pattern results (occupancy_schedule, temperature_trend) — written by `analyze.py`
- `anomalies` — detected anomalies — written by `analyze.py`
- `spatial_insights` — anomalies aggregated per building with coordinates — written by `spatial.py`
- `raw_sensor_data` — partitioned table (S3 Parquet is the primary storage; this table exists for future extensions)

```bash
python scripts/migrate.py
```

## manage_partitions.py

Creates monthly partitions for the `raw_sensor_data` table. Airflow runs this automatically
at the start of every DAG run. Running it manually is only needed for the first setup.

```bash
# Create partitions for the next 3 months
python scripts/manage_partitions.py --months-ahead 3

# Also create historical partitions (for existing or backfilled data)
python scripts/manage_partitions.py --months-back 2 --months-ahead 3

# Dry run — print SQL without executing
python scripts/manage_partitions.py --months-ahead 3 --dry-run
```

## Local setup vs. acer-server

- **Local:** Docker Compose on your own machine — for development and testing
- **acer-server:** Docker Compose on `ags@acer.gonzalezsanchez.dev` — permanent deployment
  - Airflow UI: reachable via SSH tunnel or local network on port 8080 (not publicly exposed)
  - Containers restart automatically after a server reboot (`restart: unless-stopped`)
  - Never commit on the server — only `git pull`

```bash
# Deploy on the server
ssh ags@acer.gonzalezsanchez.dev
cd ~/portfolio/projects/iot-monitoring-platform/backend/project2b-behavior-analyzer
git pull origin main
docker compose -f docker/docker-compose.yml --env-file .env up -d

# View Airflow UI via SSH tunnel (on your dev machine)
ssh -L 8080:localhost:8080 ags@acer.gonzalezsanchez.dev
# Open http://localhost:8080 — user: admin
```
