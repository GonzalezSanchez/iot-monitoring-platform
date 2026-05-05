# Project 2b — Build Order

```
Project 2b — Build Order
═══════════════════════════════════════════════════════════

Doel: dezelfde analytics als project 2a (gedragspatronen detecteren uit sensor data)
      maar nu met een data engineering stack: Apache Airflow, PySpark, Power BI.
      Demonstreert dat dezelfde businesslogica met andere tools kan worden opgelost.

Rule: tests worden geschreven PARALLEL aan de code, niet achteraf.
      Elke fase eindigt met groene tests voor commit.

Phase 1: Foundation
───────────────────
  [1] Folder structure + CI setup
       backend/project2b-behavior-analyzer/
       ├── dags/                            ← Airflow DAGs
       ├── jobs/                            ← PySpark jobs
       ├── infrastructure/                  ← Terraform (RDS PostgreSQL)
       ├── tests/
       │   ├── unit/
       │   └── integration/
       ├── docker/
       │   └── docker-compose.yml           ← Airflow + PostgreSQL + Spark lokaal
       ├── reports/                         ← Power BI .pbix bestand (gitignored)
       ├── requirements.txt
       ├── requirements-dev.txt
       └── .github/workflows/ci.yml         ← ruff, mypy, pytest, terraform validate

  [2] Infrastructure — Terraform
       ├── RDS PostgreSQL (db.t3.micro, lokaal via Docker)
       ├── S3 bucket (ruwe sensor data als Parquet)
       └── IAM rollen (Airflow worker, Spark job toegang)

Phase 2: Database
─────────────────
  [3t] Tests: migrate.py
       ├── tabellen bestaan na run (local Docker PostgreSQL)
       └── tweede run gooit geen error (idempotent)
  [3] DB migration script (Python)
       └── creates: raw_sensor_data, patterns, anomalies
           (zelfde schema als project 2a — opzettelijk, toont portabiliteit)

Phase 3: PySpark jobs
─────────────────────
  [4t] Tests: extract job
       ├── leest Parquet van lokale S3-mock (MinIO)
       └── schrijft correcte rijen naar raw_sensor_data
  [4] PySpark job: Extract
       └── leest sensor events Parquet (S3) → raw_sensor_data (PostgreSQL via JDBC)

  [5t] Tests: transform job
       ├── ongeldige temperaturen gefilterd
       └── valide rijen bevatten genormaliseerde eenheden
  [5] PySpark job: Transform
       └── normalize + clean raw_sensor_data → processed_sensor_data

  [6t] Tests: analyze job
       ├── occupancy_schedule: bekende input → verwachte schedule (window functions)
       ├── temperature_trend: stijgende reeks → 'rising' (linear regression via MLlib)
       ├── anomaly: z-score ≥ 3 → severity medium (stddev + mean via Spark SQL)
       ├── anomaly: z-score ≥ 5 → severity high
       └── anomaly: < 4 metingen per kamer → geen anomalie geschreven
  [6] PySpark job: Analyze
       └── pattern detection + anomaly detection via Spark SQL + MLlib
           ├── min. 4 metingen per kamer vereist voor z-score (zelfde als project 2a)
           ├── z-score ≥ 3 → severity medium
           ├── z-score ≥ 5 → severity high
           └── schrijft naar patterns + anomalies (PostgreSQL)

Phase 4: Orkestratie (Airflow)
──────────────────────────────
  [7t] Tests: Airflow DAG structuur
       └── dag.test_cycle() → geen cyclus
       └── alle tasks aanwezig en afhankelijkheden correct
  [7] Airflow DAG: behavior_pipeline
       ├── dags/behavior_pipeline.py
       ├── Tasks: extract_task → transform_task → analyze_task
       ├── Schedule: @weekly (elke maandag 02:00)
       └── BashOperator of SparkSubmitOperator per taak

  [8t] Tests: DAG parameters
       └── DAG accepteert start_date + end_date als conf
  [8] DAG parameterisering + retry logica
       └── retries=2, retry_delay=timedelta(minutes=5) per taak

Phase 5: Jenkins CD pipeline
─────────────────────────────
  [9] Jenkinsfile voor project 2b
       ├── Stage: Unit Tests (pytest)
       ├── Stage: Terraform Plan (RDS + S3)
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

  [13] Frontend tabs herstructureren
        └── Splits van 3 tabs naar 5: 1a (Lambda) | 1b (FastAPI) | 2a (AWS native) | 2b (Airflow+Spark) | 3 (Gateway)
            ├── ProjectTabs.jsx uitbreiden
            ├── PowerBIDashboard.jsx toevoegen (iframe uit stap [10])
            └── Project 1a opnieuw deployen naar AWS (VITE_P1A_API_ENDPOINT)

  [14] README + demo
        ├── Lokaal starten (Docker Compose: Airflow + Spark + PostgreSQL + MinIO)
        ├── DAG handmatig triggeren via Airflow UI
        ├── Power BI rapport screenshot
        ├── Grafana dashboard screenshot
        └── Vergelijking tabel: project 2a vs 2b (zelfde doel, andere tools)

═══════════════════════════════════════════════════════════
Dependencies:
  1 → 2 → 3+3t → 4+4t → 5+5t → 6+6t  (PySpark pipeline)
  3 → 7+7t → 8+8t                      (Airflow orkestratie, na DB schema)
  6,8 → 9                               (Jenkins CD, na pipeline werkend)
  6,8 → 10                              (Power BI, na data in DB)
  8,10 → 11                             (Grafana Cloud, na pipeline + data werkend)
  all → 12 → 13                         (CI + docs als laatste)

───────────────────────────────────────────────────────────
Uitbreidingen (na project 2b compleet)
───────────────────────────────────────────────────────────

  [U1] COPY binary writer — performance optimalisatie extract job
        Huidig: df.write.jdbc(...)  — simpel, correct, maar trager
        Doel:   vervang JDBC write door psycopg3 COPY FROM STDIN (FORMAT BINARY)
                → geïnspireerd op fastapi-dbuploader/src/common/batch_writer.py
                → 10-100x sneller voor bulk inserts (David Morel benchmarks)
        Scope:  alleen jobs/extract.py — schema, partities, DAG blijven identiek
        Verhaal: correctheid eerst (JDBC), daarna performance (COPY binary)
                 — dezelfde iteratieve aanpak als fastapi-dbuploader project
```
