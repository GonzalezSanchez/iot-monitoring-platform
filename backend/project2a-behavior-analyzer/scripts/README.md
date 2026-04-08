# Scripts

## Overview

| Script | Purpose | When to run |
|--------|---------|-------------|
| `migrate.py` | Creates/updates all database tables and indexes | Once before first run, and after every schema change |
| `seed.py` | Seeds test sensor data into DynamoDB for local development | Optional — only for local testing with real DynamoDB |

## Execution order

For a fresh local setup:

```bash
# 1. Start local PostgreSQL
docker compose -f docker/docker-compose.yml up -d

# 2. Create tables
python scripts/migrate.py

# 3. (Optional) seed test data
python scripts/seed.py
```

## Notes

- `migrate.py` is idempotent — safe to run multiple times (`CREATE TABLE IF NOT EXISTS`)
- In production (AWS): `migrate.py` runs once manually after infrastructure is provisioned
- Never run `seed.py` against production data
