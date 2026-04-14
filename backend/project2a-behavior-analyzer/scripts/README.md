# Scripts

## Overview

| Script | Purpose | When to run |
|--------|---------|-------------|
| `deploy.sh` | Runs `terraform init/plan/apply` to provision all infrastructure | Before a demo or when infrastructure changes are needed |
| `destroy.sh` | Runs `terraform destroy` to tear down all resources | After a demo to stop AWS costs (~$15/month) |
| `migrate.py` | Creates/updates all database tables and indexes | Once before first run, and after every schema change |
| `seed_dynamodb.py` | Populates `prod-SensorEvents` with 30 days of realistic historical data | Once before first ETL run — required for meaningful pattern detection |

## Deploy infrastructure (AWS)

```bash
# Deploy to prod (default)
./scripts/deploy.sh prod

# Deploy to dev
./scripts/deploy.sh dev
```

On first run the script creates `infrastructure/terraform.tfvars` and prompts for the DynamoDB table ARN (from project 1a).
Aurora endpoint is wired directly into the Secrets Manager secret by Terraform — no manual update needed.

## Demo workflow

This project is deployed on-demand for demos only, to keep AWS costs near zero.

```bash
# Before demo: deploy everything (~5 min)
./scripts/deploy.sh prod
python scripts/migrate.py

# Seed historical data (required on first deploy — only needed once)
python scripts/seed_dynamodb.py

# After demo: destroy everything to stop costs
./scripts/destroy.sh prod
```

Estimated cost while deployed: ~$15/month (VPC endpoints ~$14, Aurora serverless ~$1 when idle).

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

## Terraform state

State is stored locally in `infrastructure/terraform.tfstate` (git-ignored).
For team use, configure an S3 backend in `infrastructure/providers.tf`:

```hcl
backend "s3" {
  bucket = "my-terraform-state"
  key    = "p2a/terraform.tfstate"
  region = "eu-central-1"
}
```

## Notes

- `migrate.py` is idempotent — safe to run multiple times (`CREATE TABLE IF NOT EXISTS`)
- In production (AWS): `migrate.py` runs once manually after infrastructure is provisioned
- Never run `seed.py` against production data
