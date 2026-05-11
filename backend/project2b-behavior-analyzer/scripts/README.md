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

## Setup (eerste keer)

Prerequisites:
- Docker Compose services draaien: `docker compose -f docker/docker-compose.yml up -d`
- `.env` bestand aangemaakt (kopieer van `.env.example` en vul in)
- AWS credentials geconfigureerd (`aws sts get-caller-identity` moet werken)

```bash
cd backend/project2b-behavior-analyzer

# 1. Start services (Airflow + PostgreSQL)
docker compose -f docker/docker-compose.yml up -d

# 2. Maak database tabellen aan
python scripts/migrate.py

# 3. Maak partities aan voor de komende 3 maanden
python scripts/manage_partitions.py --months-ahead 3

# 4. Seed testdata in DynamoDB (eenmalig — hergebruik project 2a script)
python backend/project2a-behavior-analyzer/scripts/seed_dynamodb.py

# 5. Draai de pipeline
spark-submit --master local[*] jobs/extract.py
spark-submit --master local[*] jobs/transform.py
spark-submit --master local[*] jobs/analyze.py
```

## migrate.py

Maakt alle tabellen en indexes aan in PostgreSQL. Idempotent — veilig om meerdere keren te draaien.

```bash
python scripts/migrate.py
```

## manage_partitions.py

Maakt maandelijkse partities aan voor de `raw_sensor_data` tabel. Airflow draait dit automatisch
aan het begin van elke DAG run. Handmatig draaien is alleen nodig voor de eerste setup.

```bash
# Maak partities voor de komende 3 maanden
python scripts/manage_partitions.py --months-ahead 3

# Dry run — print SQL zonder uit te voeren
python scripts/manage_partitions.py --months-ahead 3 --dry-run
```

## Lokale setup vs. acer-server

- **Lokaal:** Docker Compose op je eigen machine — voor development en testen
- **acer-server:** Docker Compose op `ags@acer.gonzalezsanchez.dev` — permanente deployment
  - Deploy: `git pull && docker compose -f docker/docker-compose.yml up -d`
  - Nooit committen op de server — alleen `git pull`
