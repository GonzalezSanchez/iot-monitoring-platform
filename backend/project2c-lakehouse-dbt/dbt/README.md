# dbt — Silver → Gold transformations

dbt transforms the cleaned Silver data into analytical Gold models in Unity Catalog.

**Stack**: dbt-core 1.9.4 + dbt-databricks 1.9.5
**Target**: `p2c_dev` catalog, SQL Warehouse
**Authentication**: Databricks PAT token via `.env`

## Model Architecture

```
silver.sensor_events (bron)
        │
        ▼
staging/stg_sensor_events          → view in silver schema
        │
        ▼
intermediate/int_sensor_events_with_stats   → ephemeral (CTE, no table)
        │
        ├──▶ gold.fact_anomalies    → incremental tabel
        ├──▶ gold.fact_patterns     → incremental tabel (merge per uur)
        ├──▶ gold.dim_rooms         → statische tabel
        └──▶ gold.dim_buildings     → statische tabel
```

### Models

| Model | Materialization | Schema | Description |
|-------|---------------|--------|--------------|
| `stg_sensor_events` | view | silver | Clean interface on the Silver source |
| `int_sensor_events_with_stats` | ephemeral | — | Window functions: mean + stddev per room+sensor_type |
| `fact_anomalies` | incremental | gold | Z-scores + anomaly flag per event (`\|z\| > 2.5`) |
| `fact_patterns` | incremental (merge) | gold | Hourly aggregations: avg/min/max/count |
| `dim_rooms` | table | gold | 10 rooms across 2 buildings |
| `dim_buildings` | table | gold | 2 buildings (Main Office, Warehouse) |

### Data tests
22 tests defined in `models/staging/sources.yml` and `models/marts/_schema.yml`:
- `unique` + `not_null` on all primary keys
- `accepted_values` on `sensor_type` (temperature, co2, occupancy, humidity)

## Setup

### Requirements
- Python venv with dbt-core + dbt-databricks (see `../requirements.txt`)
- `.env` with the correct values (see `../.env.example`)

### Environment variables (`.env`)
```
DATABRICKS_HOST=https://<workspace>.azuredatabricks.net
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/<warehouse-id>
DATABRICKS_TOKEN=<pat-token>
```

Create the PAT token via the Databricks UI: **Settings → Developer → Access tokens**.
Token validity: 90 days. Renew before it expires.

## Commands

Always run from the `dbt/` directory. **Always** use `.venv/bin/dbt` — not the global `dbt` binary (that's dbt-fusion 2.0, incompatible with this project).

```bash
cd backend/project2c-lakehouse-dbt

# Load the environment variables
source .env  # or: set -a && source .env && set +a

# Run dbt
.venv/bin/dbt run  --profiles-dir dbt  --project-dir dbt
.venv/bin/dbt test --profiles-dir dbt  --project-dir dbt

# Run just one model
.venv/bin/dbt run --profiles-dir dbt --project-dir dbt --select fact_anomalies

# Inspect lineage
.venv/bin/dbt docs generate --profiles-dir dbt --project-dir dbt
.venv/bin/dbt docs serve    --profiles-dir dbt --project-dir dbt
```

## Schema naming

By default, dbt combines `target.schema + custom_schema` → e.g. `gold_silver`. The macro `macros/generate_schema_name.sql` overrides this: `+schema: silver` yields exactly the schema `silver` in Unity Catalog.

## Directory Structure

```
dbt/
├── dbt_project.yml              # Project configuration + materialization defaults
├── profiles.yml                 # Databricks connection settings
├── macros/
│   └── generate_schema_name.sql # Schema-naming override
└── models/
    ├── staging/
    │   ├── sources.yml          # Source declaration + tests on Silver
    │   └── stg_sensor_events.sql
    ├── intermediate/
    │   └── int_sensor_events_with_stats.sql
    └── marts/
        ├── _schema.yml          # Tests on Gold models
        ├── fact_anomalies.sql
        ├── fact_patterns.sql
        ├── dim_rooms.sql
        └── dim_buildings.sql
```

## Extensions

- **CI/CD**: dbt run as a step in GitHub Actions after the DABs pipeline (service principal auth)
- **dbt Cloud**: replace local PAT auth with dbt Cloud job scheduling
- **Exposures**: declare Power BI dashboards as dbt exposures for full lineage
- **Snapshots**: Type-2 SCD for `dim_rooms` in case room configuration can change
