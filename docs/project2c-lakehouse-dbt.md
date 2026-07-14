# Project 2c: Azure Databricks Lakehouse + dbt

## Description

The same IoT sensor domain as projects 2a/2b — 10 simulated rooms with
temperature, CO₂, occupancy, and humidity sensors — rebuilt as a lakehouse on a
fully managed Azure stack: Databricks with Delta Lake, Unity Catalog governance,
and dbt for the transformation layer. Completes the analytics trio: AWS-native
(2a), self-hosted data engineering (2b), managed lakehouse (2c).

| | Project 2b | Project 2c |
|---|---|---|
| Cloud | AWS + own server | Azure (fully managed) |
| Ingestion | DynamoDB → PySpark → S3 | Python script → ADLS Gen2 (Auto Loader) |
| Orchestration | Apache Airflow | Databricks Jobs (DABs) |
| Transformation | PySpark + dbt-postgres | dbt-databricks (SQL Warehouse) |
| Data modeling | Flat tables | Dimensional (fact + dim) |
| Lineage | dbt docs (manual) | Unity Catalog (automatic) |
| Serving layer | PostgreSQL | SQL Warehouse |

## Status

**Live** — results feed the "Databricks + dbt" tab on
[iot.gonzalezsanchez.dev](https://iot.gonzalezsanchez.dev). The pipeline
schedule is deliberately **paused** (each run costs ~€4 in cluster time); runs
are triggered manually via the Databricks UI or
`databricks bundle run p2c_weekly_pipeline`.

## Tech Stack

| Layer | Tool | Purpose |
|---|---|---|
| Ingestion | Python script + ADLS Gen2 | Simulated sensor JSON → Bronze |
| Storage | Delta Lake (ADLS Gen2) | ACID tables, time travel |
| Governance | Unity Catalog | Lineage, access control, 3-part SQL path |
| Batch processing | PySpark (Databricks Job) | Bronze → Silver (WAP pattern) |
| Transformation | dbt-databricks | Silver → Gold (fact + dim) |
| Orchestration | Databricks Jobs (DABs) | Dependency chain + failure alerts |
| Infrastructure | Terraform | Workspace, ADLS, Key Vault, SQL Warehouse |
| Serving | SQL Warehouse | Power BI DirectQuery |

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
Delta Lake Gold    (p2c_prod.gold.fact_anomalies, fact_patterns, dim_rooms, dim_buildings)
    ↓ DirectQuery (Entra ID / OAuth)
Power BI
```

## Key Design Decisions

**Medallion architecture (Bronze/Silver/Gold)** — raw data stays replayable in
Bronze; Silver is typed, deduplicated, and validated; Gold is dimensional
(fact + dim), modeled for the consumer instead of the producer.

**Write-Audit-Publish (WAP) in the Silver step** — a batch is validated *before*
it is merged: good records go through an idempotent `MERGE`, invalid records go
to a quarantine table that is never deleted. The same never-lose-data
philosophy returns as dropped-row counting in 2b and the DLQ topic in 3b.

**dbt on the SQL Warehouse for Gold** — transformations as tested, incremental
SQL models (22 data tests) instead of imperative jobs; `dbt parse` runs in CI
without a live connection.

**Unity Catalog** — automatic lineage and access control came free with the
platform choice; in 2b the same governance questions are manual work.

**DABs (Databricks Asset Bundles)** — the job definition is code
(`databricks.yml`), deployed with `databricks bundle deploy`; the workspace UI
is a view, not the source of truth. Mirrors the IaC discipline of the rest of
the platform.

**Cost control by design** — schedule paused (cron kept in config for
reference), single-node `Standard_D4s_v3` job cluster (the smallest supported
size in this workspace), NAT Gateway removed as idle cost. Running cost:
~€7–8/month idle + ~€4 per manual run. Lesson learned: the Azure free-trial
vCPU quota (4) exactly matches D4s_v3 — trial expiry dropped the quota and
failed the pipeline with `AZURE_QUOTA_EXCEEDED_EXCEPTION`; fixed by upgrading
to pay-as-you-go (quota 10).

**Terraform with a two-step apply** — the workspace URL only exists after the
workspace is created, so provider configuration requires two phases
(documented in `infrastructure/README.md`).

**Deliberately not unit-testing Delta operations** — mocking
`DeltaTable.merge()` would only verify the mock. Business logic
(`validate_batch()`, generators, validators) is unit-tested (92% coverage);
Delta/Auto Loader calls are integration-tested on the real cluster, which
caught two real bugs that mocks would have hidden.

## Credentials

Two separate credential paths, both least-privilege:

- **Databricks PAT** — day-to-day work (bundle deploy, job runs, SQL Warehouse);
  expires ~September 2026.
- **Service principal `p2c-sp`** — Owner on resource group `rg-p2c-iot` only,
  needed exclusively for `terraform apply`; lives in the gitignored
  `infrastructure/.env` (`ARM_*` variables, `source .env` before running
  Terraform).

## More

Setup, test commands, and infrastructure notes:
[project README](../backend/project2c-lakehouse-dbt/README.md) ·
screenshots: `docs/screenshots/project2c/`
