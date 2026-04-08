# Scripts

## Overview

| Script | Purpose | When to run |
|--------|---------|-------------|
| `deploy.sh` | Deploys all CloudFormation stacks in the correct order (vpc → database → iam → secrets) | Before a demo or when infrastructure changes are needed |
| `destroy.sh` | Destroys all CloudFormation stacks in reverse order | After a demo to stop AWS costs (~$15/month) |
| `migrate.py` | Creates/updates all database tables and indexes | Once before first run, and after every schema change |
| `seed.py` | Seeds test sensor data into DynamoDB for local development | Optional — only for local testing with real DynamoDB |

## Deploy infrastructure (AWS)

```bash
# Deploy all stacks to prod (default)
./scripts/deploy.sh prod

# Deploy to dev
./scripts/deploy.sh dev
```

The script deploys stacks in dependency order: vpc → database → iam → secrets.
After running, update the `p2a-prod-db-credentials` secret with the real Aurora endpoint and password (the script prints the exact command).

## Demo workflow

This project is deployed on-demand for demos only, to keep AWS costs near zero.

```bash
# Before demo: deploy everything (~5 min)
./scripts/deploy.sh prod
python scripts/migrate.py

# After demo: destroy everything to stop costs
./scripts/destroy.sh prod
```

Estimated cost while deployed: ~$15/month (VPC endpoints only; Aurora auto-pauses after 5 min).

## Local development

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
