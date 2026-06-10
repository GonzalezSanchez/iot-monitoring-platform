# Project 2c — Azure Databricks Lakehouse + dbt

IoT sensor data pipeline on a fully managed Azure stack. Same domain as [project 2b](../../docs/project2b-behavior-analyzer.md) — 10 simulated rooms with temperature, CO₂, occupancy, and humidity sensors — but rebuilt on Azure Databricks with Delta Lake, Unity Catalog, and dbt.

## Stack

| Layer | Tool | Purpose |
|---|---|---|
| Ingestion | Python script + ADLS Gen2 | Simulated sensor JSON → Bronze |
| Storage | Delta Lake (ADLS Gen2) | ACID tables, time travel |
| Governance | Unity Catalog | Lineage, access control, 3-part SQL path |
| Batch processing | PySpark (Databricks Job) | Bronze → Silver (WAP pattern) |
| Transformation | dbt-databricks | Silver → Gold (fact + dim) |
| Orchestration | Databricks Jobs (DABs) | Dependency chain + failure alerts |
| Infrastructure | Terraform | Full IaC — workspace, ADLS, Key Vault, SQL Warehouse |
| Serving | SQL Warehouse | Power BI DirectQuery |
| Visualization | Power BI | Anomaly + pattern reports |

## Architecture

```
Python script
    ↓ JSON files
ADLS Gen2 Bronze  ←── Auto Loader (cloudFiles + checkpointLocation)
    ↓
Delta Lake Bronze  (p2c_prod.bronze.sensor_events) — raw, no schema enforcement
    ↓ PySpark Job — WAP pattern
Delta Lake Silver  (p2c_prod.silver.sensor_events) — cleaned, MERGE idempotent
    ↓ Quarantine → p2c_prod.silver.sensor_events_quarantine
    ↓ dbt-databricks — incremental models
Delta Lake Gold    (p2c_prod.gold.fact_anomalies, dim_rooms, ...)
    ↓ DirectQuery (Entra ID / OAuth)
Power BI
```

## Bronze / Silver / Gold responsibilities

| Layer | Table | Responsibility |
|---|---|---|
| Bronze | `sensor_events` | Raw JSON as-is, no transformations. Replayable. |
| Silver | `sensor_events` | Typed, deduplicated, validated. Good records only. |
| Silver | `sensor_events_quarantine` | Invalid records for manual review. Never deleted. |
| Gold | `fact_anomalies` | Z-score anomaly detection per room + sensor type. |
| Gold | `fact_patterns` | Hourly window aggregations. |
| Gold | `dim_rooms` | Room metadata. |
| Gold | `dim_buildings` | Building metadata. |

## Local development

### Prerequisites
- Python 3.11+
- Terraform >= 1.9.0
- dbt-databricks 1.9.5 (see `requirements.txt`)
- Active Azure subscription + Databricks workspace

### Setup

```bash
# 1. Install Python dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# 2. Configure environment
cp .env.example .env
# Fill in DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_HTTP_PATH, etc.

# 3. Provision infrastructure (Fase 1)
cd infrastructure
cp terraform.tfvars.example terraform.tfvars
# Fill in terraform.tfvars
terraform init
terraform plan
terraform apply

# 4. Run dbt
cd ../dbt
dbt debug
dbt compile
dbt run
dbt test
```

### Run tests

```bash
pytest tests/ -v --cov=scripts --cov=jobs --cov-report=term-missing
```

### Run linting

```bash
ruff check scripts/ jobs/ tests/
mypy scripts/ jobs/
```

## CI/CD

CI runs on every push via GitHub Actions (`.github/workflows/ci.yml`):
- ruff + mypy on `scripts/` and `jobs/`
- pytest with coverage
- `dbt parse` — verifies model syntax without a live connection
- Terraform validate

CD (Fase 7): `databricks bundle deploy --target prod` via DABs on push to `main`.

## Differences from Project 2b

| | Project 2b | Project 2c |
|---|---|---|
| Cloud | AWS + own server | Azure (fully managed) |
| Ingestion | DynamoDB → PySpark → S3 | Python script → ADLS Gen2 |
| Orchestration | Apache Airflow | Databricks Jobs (DABs) |
| Transformation | PySpark + dbt-postgres | dbt-databricks (SQL Warehouse) |
| Data modeling | Flat tables | Dimensional (fact + dim) |
| Lineage | dbt docs (manual) | Unity Catalog (automatic) |
| Serving layer | PostgreSQL | SQL Warehouse |
