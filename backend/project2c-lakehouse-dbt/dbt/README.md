# dbt — Silver → Gold transformaties

dbt transformeert de gecleande Silver data naar analytische Gold modellen in Unity Catalog.

**Stack**: dbt-core 1.9.4 + dbt-databricks 1.9.5
**Target**: `p2c_dev` catalog, SQL Warehouse
**Authenticatie**: Databricks PAT token via `.env`

## Modelarchitectuur

```
silver.sensor_events (bron)
        │
        ▼
staging/stg_sensor_events          → view in silver schema
        │
        ▼
intermediate/int_sensor_events_with_stats   → ephemeral (CTE, geen tabel)
        │
        ├──▶ gold.fact_anomalies    → incremental tabel
        ├──▶ gold.fact_patterns     → incremental tabel (merge per uur)
        ├──▶ gold.dim_rooms         → statische tabel
        └──▶ gold.dim_buildings     → statische tabel
```

### Modellen

| Model | Materialisatie | Schema | Beschrijving |
|-------|---------------|--------|--------------|
| `stg_sensor_events` | view | silver | Schone interface op de Silver bron |
| `int_sensor_events_with_stats` | ephemeral | — | Window functions: mean + stddev per room+sensor_type |
| `fact_anomalies` | incremental | gold | Z-scores + anomalie-flag per event (`\|z\| > 2.5`) |
| `fact_patterns` | incremental (merge) | gold | Uurlijkse aggregaties: avg/min/max/count |
| `dim_rooms` | table | gold | 10 kamers in 2 gebouwen |
| `dim_buildings` | table | gold | 2 gebouwen (Main Office, Warehouse) |

### Data tests
22 tests gedefinieerd in `models/staging/sources.yml` en `models/marts/_schema.yml`:
- `unique` + `not_null` op alle primaire sleutels
- `accepted_values` op `sensor_type` (temperature, co2, occupancy, humidity)

## Setup

### Vereisten
- Python venv met dbt-core + dbt-databricks (zie `../requirements.txt`)
- `.env` met de juiste waarden (zie `../.env.example`)

### Omgevingsvariabelen (`.env`)
```
DATABRICKS_HOST=https://<workspace>.azuredatabricks.net
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/<warehouse-id>
DATABRICKS_TOKEN=<pat-token>
```

Het PAT token maak je aan via de Databricks UI: **Settings → Developer → Access tokens**.
Token geldigheid: 90 dagen. Vernieuw vóór verloopdatum.

## Commando's

Altijd uitvoeren vanuit de `dbt/` map. Gebruik **altijd** `.venv/bin/dbt` — niet de globale `dbt` binary (die is dbt-fusion 2.0, incompatibel met dit project).

```bash
cd backend/project2c-lakehouse-dbt

# Laad de omgevingsvariabelen
source .env  # of: set -a && source .env && set +a

# dbt uitvoeren
.venv/bin/dbt run  --profiles-dir dbt  --project-dir dbt
.venv/bin/dbt test --profiles-dir dbt  --project-dir dbt

# Enkel één model draaien
.venv/bin/dbt run --profiles-dir dbt --project-dir dbt --select fact_anomalies

# Lineage inspecteren
.venv/bin/dbt docs generate --profiles-dir dbt --project-dir dbt
.venv/bin/dbt docs serve    --profiles-dir dbt --project-dir dbt
```

## Schema-naming

dbt combineert standaard `target.schema + custom_schema` → bijv. `gold_silver`. De macro `macros/generate_schema_name.sql` overschrijft dit: `+schema: silver` geeft exact het schema `silver` in Unity Catalog.

## Mapstructuur

```
dbt/
├── dbt_project.yml              # Projectconfiguratie + materalisatie-defaults
├── profiles.yml                 # Databricks verbindingsinstellingen
├── macros/
│   └── generate_schema_name.sql # Schema-naming override
└── models/
    ├── staging/
    │   ├── sources.yml          # Brondeclaratie + tests op Silver
    │   └── stg_sensor_events.sql
    ├── intermediate/
    │   └── int_sensor_events_with_stats.sql
    └── marts/
        ├── _schema.yml          # Tests op Gold modellen
        ├── fact_anomalies.sql
        ├── fact_patterns.sql
        ├── dim_rooms.sql
        └── dim_buildings.sql
```

## Uitbreidingen

- **CI/CD**: dbt run als stap in GitHub Actions na de DABs pipeline (service principal auth)
- **dbt Cloud**: vervang lokale PAT auth door dbt Cloud job scheduling
- **Exposures**: declareer Power BI dashboards als dbt exposures voor volledige lineage
- **Snapshots**: Type-2 SCD voor `dim_rooms` als kamerconfiguratie kan veranderen
