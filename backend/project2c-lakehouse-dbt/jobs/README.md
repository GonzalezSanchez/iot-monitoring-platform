# Jobs — Databricks PySpark pipeline

The three PySpark jobs make up the Bronze → Silver pipeline. They run as Databricks Jobs via DABs (`databricks.yml`).

## Jobs

| Job | Input | Output | Description |
|-----|-------|--------|--------------|
| `bronze_autoloader.py` | ADLS Bronze (JSON) | `bronze.sensor_events` | Auto Loader incrementally reads new JSON files via `cloudFiles` |
| `silver_wap.py` | `bronze.sensor_events` | `silver.sensor_events` + `silver.sensor_events_quarantine` | WAP pattern: validate each row, good records via MERGE, bad ones to quarantine |
| `optimize_vacuum.py` | `silver.sensor_events` | — | `OPTIMIZE` (compaction) + `VACUUM` (cleaning up old files) |

## Execution

Jobs run via DABs:
```bash
databricks bundle run iot_pipeline
```

Or individually:
```bash
databricks bundle run iot_pipeline --task bronze_autoloader
databricks bundle run iot_pipeline --task silver_wap
```

## WAP pattern (`silver_wap.py`)

Write-Audit-Publish guarantees data quality:

```
Bronze batch
    ↓ validate_batch()
    ├── good records  → MERGE INTO silver.sensor_events    (idempotent on event_id)
    └── bad records   → APPEND silver.sensor_events_quarantine (never deleted)
```

Validation rules:
- `event_id`, `room_id`, `sensor_type`, `value` must not be null
- `room_id` must not be empty
- `sensor_type` must be one of: `temperature`, `co2`, `occupancy`, `humidity`
- `timestamp` must be parseable as ISO-8601

## Test Strategy

### What is unit-tested

`validate_batch()` contains all the business logic and is fully unit-testable: pure PySpark transformations, no Delta or Azure connection needed.

```bash
pytest tests/unit/test_silver_wap.py -v
```

43 tests, 94% coverage on `silver_wap.py`.

### What isn't unit-tested

| Function | Reason |
|---------|-------|
| `ensure_tables()` | Requires a live Unity Catalog for `CREATE TABLE IF NOT EXISTS` |
| `merge_good_records()` | Requires `DeltaTable.forName()` — live Delta catalog |
| `write_quarantine()` | Requires `df.write.format("delta").saveAsTable()` — live Delta |
| `run()`, `main()` | Orchestration of the above |
| `bronze_autoloader.py` | Requires `cloudFiles` (Auto Loader) — Databricks only |
| `optimize_vacuum.py` | Requires `OPTIMIZE`/`VACUUM` SQL — Delta only |

**Why no mocks?** Mocking `DeltaTable.merge()` only tests whether the mock gets called — not whether the Delta operation actually works correctly. During development, two real bugs were found via integration testing that mocks would never catch (schema mismatch, missing `SINGLE_USER` cluster mode).

These functions are marked with `# pragma: no cover` and integration-tested after `terraform apply`.
