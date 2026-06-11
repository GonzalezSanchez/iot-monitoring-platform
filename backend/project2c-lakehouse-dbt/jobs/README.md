# Jobs — Databricks PySpark pipeline

De drie PySpark jobs vormen de Bronze → Silver pipeline. Ze draaien als Databricks Jobs via DABs (`databricks.yml`).

## Jobs

| Job | Input | Output | Beschrijving |
|-----|-------|--------|--------------|
| `bronze_autoloader.py` | ADLS Bronze (JSON) | `bronze.sensor_events` | Auto Loader leest nieuwe JSON bestanden incrementeel via `cloudFiles` |
| `silver_wap.py` | `bronze.sensor_events` | `silver.sensor_events` + `silver.sensor_events_quarantine` | WAP patroon: valideer elke rij, goede records via MERGE, slechte naar quarantine |
| `optimize_vacuum.py` | `silver.sensor_events` | — | `OPTIMIZE` (compaction) + `VACUUM` (oude bestanden opruimen) |

## Uitvoering

Jobs draaien via DABs:
```bash
databricks bundle run iot_pipeline
```

Of individueel:
```bash
databricks bundle run iot_pipeline --task bronze_autoloader
databricks bundle run iot_pipeline --task silver_wap
```

## WAP patroon (`silver_wap.py`)

Write-Audit-Publish garandeert datakwaliteit:

```
Bronze batch
    ↓ validate_batch()
    ├── good records  → MERGE INTO silver.sensor_events    (idempotent op event_id)
    └── bad records   → APPEND silver.sensor_events_quarantine (nooit verwijderd)
```

Validatieregels:
- `event_id`, `room_id`, `sensor_type`, `value` mogen niet null zijn
- `room_id` mag niet leeg zijn
- `sensor_type` moet een van: `temperature`, `co2`, `occupancy`, `humidity`
- `timestamp` moet parseerbaar zijn als ISO-8601

## Teststrategie

### Wat wel unit-getest wordt

`validate_batch()` bevat alle business logica en is volledig unit-testbaar: pure PySpark transformaties, geen Delta of Azure verbinding nodig.

```bash
pytest tests/unit/test_silver_wap.py -v
```

43 tests, 94% coverage op `silver_wap.py`.

### Wat niet unit-getest wordt

| Functie | Reden |
|---------|-------|
| `ensure_tables()` | Vereist live Unity Catalog voor `CREATE TABLE IF NOT EXISTS` |
| `merge_good_records()` | Vereist `DeltaTable.forName()` — live Delta catalog |
| `write_quarantine()` | Vereist `df.write.format("delta").saveAsTable()` — live Delta |
| `run()`, `main()` | Orchestratie van bovenstaande |
| `bronze_autoloader.py` | Vereist `cloudFiles` (Auto Loader) — alleen op Databricks |
| `optimize_vacuum.py` | Vereist `OPTIMIZE`/`VACUUM` SQL — alleen op Delta |

**Waarom geen mocks?** `DeltaTable.merge()` mocken test alleen of de mock aangeroepen wordt — niet of de Delta operatie correct werkt. Tijdens ontwikkeling zijn twee echte bugs gevonden via integration testing die mocks nooit zouden vangen (schema mismatch, ontbrekende `SINGLE_USER` cluster mode).

Deze functies zijn gemarkeerd met `# pragma: no cover` en integration-getest na `terraform apply`.
