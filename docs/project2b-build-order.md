# Project 2b — Build Order

```
Project 2b — Build Order
═══════════════════════════════════════════════════════════

Doel: dezelfde analytics als project 2a (gedragspatronen detecteren uit sensor data)
      maar nu met een data engineering stack: Apache Airflow, PySpark, Power BI.
      Demonstreert dat dezelfde businesslogica met andere tools kan worden opgelost.

Architectuur: data lake patroon met drie lagen
  DynamoDB → S3/raw (Parquet) → S3/processed (Parquet) → PostgreSQL (serving layer)

  Waarom PostgreSQL alleen aan het einde?
  Power BI kan S3 Parquet niet rechtstreeks bevragen — het heeft een SQL endpoint nodig.
  Alternatieven (Athena, Redshift) brengen extra AWS kosten. PostgreSQL draait self-hosted
  op acer-server via Docker (altijd live, geen destroy cyclus, geen RDS kosten ~€15–20/maand).

Rule: tests worden geschreven PARALLEL aan de code, niet achteraf.
      Elke fase eindigt met groene tests voor commit.

Phase 1: Foundation                                                    [DONE]
───────────────────
  ✓ [1] Folder structure + CI setup
       backend/project2b-behavior-analyzer/
       ├── dags/                            ← Airflow DAGs
       ├── jobs/                            ← PySpark jobs
       ├── infrastructure/                  ← Terraform (S3 + IAM)
       ├── tests/
       │   ├── unit/
       │   └── integration/
       ├── docker/
       │   └── docker-compose.yml           ← PostgreSQL (pgvector/pgvector:pg16)
       ├── reports/                         ← Power BI .pbix bestand (gitignored)
       ├── requirements.txt
       ├── requirements-dev.txt
       └── .github/workflows/ci.yml         ← ruff, mypy, pytest, terraform validate

  ✓ [2] Infrastructure — Terraform
       ├── S3 bucket: p2b-prod-sensor-events (raw/ + processed/ Parquet)
       └── IAM user: Airflow worker (S3 read/write + DynamoDB read)
       Note: PostgreSQL draait via Docker Compose op acer-server — geen RDS, geen AWS kosten

Phase 2: Database                                                      [DONE]
─────────────────
  ✓ [3t] Tests: migrate.py
       ├── tabellen bestaan na run (local Docker PostgreSQL)
       └── tweede run gooit geen error (idempotent)
  ✓ [3] DB migration script (Python)
       └── creates: raw_sensor_data (gepartitioneerd), patterns, anomalies
           (zelfde schema als project 2a — opzettelijk, toont portabiliteit)
           Note: raw_sensor_data aanwezig in DB; S3 Parquet is de primaire tussenopslag

  Testdata: hergebruik backend/project2a-behavior-analyzer/scripts/seed_dynamodb.py
       └── zelfde DynamoDB tabel (prod-SensorEvents) — geen aparte seed script nodig

Phase 3: PySpark jobs                                                  [DONE]
─────────────────────
  ✓ [4t] Tests: extract job
       ├── leest sensor events van DynamoDB (beide event formats: seed + project 1b)
       ├── schrijft correct Parquet schema naar S3 landing zone
       └── idempotent: re-run overschrijft alleen de getroffen maandpartities
  ✓ [4] PySpark job: Extract
       └── DynamoDB (prod-SensorEvents) → S3/raw Parquet
           gepartitioneerd op jaar/maand, dynamic partition overwrite
           Verwerkt seed format (payload JSON) en project 1b format (sensor_type + value)

  spark-submit command:
  PACKAGES="org.apache.hadoop:hadoop-aws:3.4.2,com.amazonaws:aws-java-sdk-bundle:1.12.262,org.postgresql:postgresql:42.7.3"
  S3A="com.amazonaws.auth.DefaultAWSCredentialsProviderChain"
  spark-submit --packages $PACKAGES --conf spark.hadoop.fs.s3a.aws.credentials.provider=$S3A jobs/extract.py

  ✓ [5t] Tests: transform job
       ├── ongeldige temperaturen (null, buiten −10°C–60°C) gefilterd
       ├── ongeldige vochtigheid (null, buiten 0–100%) gefilterd
       └── valide rijen bevatten hernoemde kolommen (temperature_c, humidity_pct)
  ✓ [5] PySpark job: Transform
       └── S3/raw Parquet → valideren + schoonmaken → S3/processed Parquet
           dynamic partition overwrite, gepartitioneerd op jaar/maand

  ✓ [6t] Tests: analyze job
       ├── occupancy_schedule: bekende input → verwachte schedule (window functions)
       ├── temperature_trend: stijgende reeks → 'rising' (regr_slope via Spark SQL)
       ├── anomaly: z-score ≥ 3 → severity medium (populatie stddev via window)
       ├── anomaly: z-score ≥ 5 → severity high
       └── anomaly: < 4 metingen per kamer → geen anomalie geschreven
  ✓ [6] PySpark job: Analyze
       └── S3/processed Parquet → patronen + anomaliedetectie → PostgreSQL (serving layer)
           ├── occupancy_schedule: gemiddelde bezetting per (kamer, dag, uur)
           ├── temperature_trend: regressiehelling via regr_slope (Spark SQL aggregate)
           ├── z-score anomaliedetectie: min. 4 metingen, medium ≥ 3, high ≥ 5
           └── schrijft naar patterns + anomalies via JDBC (stringtype=unspecified voor jsonb)

  Eerste productierun resultaten (mei 2026):
       12.744 extracted → 12.715 processed (29 dropped) → 5+5 patterns, 22 anomalies

Phase 4: Orkestratie (Airflow)                                         [DONE]
──────────────────────────────
  ✓ [7t] Tests: Airflow DAG structuur
       └── dag.test_cycle() → geen cyclus
       └── alle tasks aanwezig en afhankelijkheden correct
  ✓ [7] Airflow DAG: behavior_pipeline
       ├── dags/behavior_pipeline.py
       ├── Tasks: manage_partitions → extract → transform → analyze
       ├── Schedule: @weekly (elke maandag 02:00)
       └── BashOperator per taak met spark-submit + packages

  ✓ [8t] Tests: DAG parameters
       └── DAG accepteert start_date + end_date als conf
  ✓ [8] DAG parameterisering + retry logica
       └── retries=2, retry_delay=timedelta(minutes=5) per taak

Phase 5: Jenkins CD pipeline                                           [DONE]
─────────────────────────────
  ✓ [9] Jenkinsfile voor project 2b
       ├── Stage: Unit Tests (pytest)
       ├── Stage: Terraform Plan (S3 + IAM)
       ├── Stage: Approval Gate
       ├── Stage: Terraform Apply
       └── Stage: Smoke Test (DAG trigger + status check)
       Zie: docs/jenkins-cd-pipeline.md voor volledig Jenkins setup

Phase 6: Power BI rapport
─────────────────────────
  [10] PostgreSQL → Power BI connectie + publicatie
        ├── DirectQuery op patterns en anomalies tabellen
        ├── Rapport pagina's:
        │   ├── Overzicht: patroon frequentie per kamer per week
        │   ├── Anomalieën: severity heatmap per kamer
        │   └── Trend: temperatuur trend over tijd (line chart)
        ├── .pbix bestand → reports/ (gitignored)
        ├── Publish to web → publieke iframe URL (Microsoft)
        │   └── frontend/src/pages/PowerBIDashboard.jsx (iframe embed)
        └── Screenshots → docs/screenshots/ (voor README)

───────────────────────────────────────────────────────────
Uitbreidingen Power BI rapport (na project 2b compleet)
───────────────────────────────────────────────────────────

  ✓ [U1] JSON parsing in Power Query — DONE
        Power Query M-code: `if [pattern_type] = "temperature_trend" then Json.Document([data])[direction] else null`
        → Direction kolom (rising/falling/stable) zichtbaar in Temperature Trend pagina
        Resterend (optioneel): occupancy_schedule uitklappen → heatmap dag vs uur

  [U2] Lijndiagram anomalieën over tijd
        Huidig: geen tijdsvisualisatie van anomalieën
        Doel:   lijndiagram: detected_at (dag) → aantal anomalieën
                ├── gefilterd op severity (medium vs high)
                └── per kamer als legenda

Phase 7: Observability — OpenTelemetry + Grafana Cloud
────────────────────────────────────────────────────────
  [11] OTel Collector + Grafana Cloud opstarten + dashboards configureren
        ├── OTel Collector toevoegen aan docker-compose.yml (zelfde aanpak als project 1b)
        ├── Grafana Cloud free tier — Mimir (metrics) + Loki (logs) + Tempo (traces)
        ├── Airflow integratie: DAG run durations, task success/failure
        ├── PostgreSQL integratie: query latency, connections
        ├── DAG draaien met testdata → metrics zichtbaar in Grafana
        ├── Screenshots opslaan in docs/screenshots/
        └── Stack blijft altijd live — gratis tier, geen destroy cyclus
        Zie: docs/project2b-behavior-analyzer.md → Observability sectie

Phase 8: CI/CD + Documentatie
──────────────────────────────
  [12] CI uitbreiden
        ├── Voeg project2b toe aan .github/workflows/ci.yml
        ├── ruff + mypy op dags/, jobs/
        ├── pytest tests/unit/ --cov-fail-under=80
        └── terraform validate

  ✓ [13] Frontend tabs herstructureren
        └── 5 tabs: 1a (Lambda) | 1b (FastAPI) | 2a (AWS native) | 2b (Airflow+Spark) | 4 (AI Assistant)
            ├── ProjectTabs.jsx uitgebreid
            └── Gateway tab verwijderd (project 3 = backend only)

  [14] README + demo
        ├── Screenshots Power BI rapport
        ├── Screenshots Grafana dashboard
        └── Vergelijking tabel: project 2a vs 2b (zelfde doel, andere tools)

═══════════════════════════════════════════════════════════
Dependencies:
  1 → 2 → 3+3t → 4+4t → 5+5t → 6+6t  (PySpark pipeline)
  3 → 7+7t → 8+8t                      (Airflow orkestratie, na DB schema)
  6,8 → 9                               (Jenkins CD, na pipeline werkend)
  6,8 → 10                              (Power BI, na data in DB)
  8,10 → 11                             (Grafana Cloud, na pipeline + data werkend)
  all → 12 → 13                         (CI + docs als laatste)

```
