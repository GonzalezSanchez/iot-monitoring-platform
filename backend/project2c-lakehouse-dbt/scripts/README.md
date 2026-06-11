# Scripts

Local utility scripts for development and testing. These run outside Databricks — on your laptop or a CI runner.

## Scripts overview

| Script | Phase | Purpose |
|---|---|---|
| `generate_sensor_data.py` | Fase 2 | Simulate IoT sensor events and write them as JSON to a local dir (dev) or ADLS Gen2 Bronze (prod) |
| `validate.py` | Fase 3 | Sensor event validation logic — used by unit tests and mirrored in the PySpark Silver job |

## Execution order

```
Fase 0 (now):     validate.py                 ← imported by tests, no direct execution
Fase 2:           generate_sensor_data.py     → writes JSON to ADLS Gen2 Bronze
Fase 3 onwards:   Auto Loader picks up the JSON files from Bronze automatically
                  PySpark jobs in jobs/ take over the transformation
```

## Usage

### generate_sensor_data.py

**Print to stdout** (no setup needed, useful for inspecting the data format):
```bash
python scripts/generate_sensor_data.py --count 10
```

**Write to a local directory** (mirrors the Hive-partitioned ADLS structure, no Azure needed):
```bash
python scripts/generate_sensor_data.py --count 500 --output-dir /tmp/bronze
# Creates: /tmp/bronze/year=2024/month=01/day=15/sensors_20240115T120000.json
```

**Write to ADLS Gen2 Bronze** (requires provisioned infrastructure from Fase 1):
```bash
# 1. Authenticate with Azure (once per session):
az login

# 2. Fill in .env with AZURE_STORAGE_ACCOUNT_NAME from terraform output:
terraform -chdir=infrastructure output adls_storage_account_name

# 3. Run the generator:
python scripts/generate_sensor_data.py --count 1000 --adls
```

Authentication uses `DefaultAzureCredential` from `azure-identity`:
- **Local**: picks up `az login` automatically — no keys or tokens in code
- **Databricks Job**: picks up the Access Connector Managed Identity automatically

The `--adls` flag reads `AZURE_STORAGE_ACCOUNT_NAME` from `.env` (or environment).
The container defaults to `bronze`; override with `AZURE_STORAGE_CONTAINER_BRONZE`.

### validate.py

Not meant to be executed directly — it is imported by `tests/unit/test_sensor_schema.py`.

The `validate_sensor_event()` and `split_wap()` functions define the same rules that the
PySpark Silver job applies in Fase 3. When adding a new validation rule, add it here first
and write a test before touching the Spark job — keeps the logic in one place and testable
without a Spark context.
