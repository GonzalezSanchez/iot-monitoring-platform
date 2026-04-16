# Scripts

## Overview

| Script | Purpose | When to run |
|--------|---------|-------------|
| `build.sh` | Packages Lambda source files into `dist/staging/` | Automatically called by `deploy.sh` |
| `deploy.sh` | Builds packages + runs `terraform init/plan/apply` | Before a demo or when infrastructure changes are needed |
| `destroy.sh` | Runs `terraform destroy` to tear down all resources | After a demo to stop AWS costs (~$15/month) |
| `migrate.py` | Creates/updates all database tables and indexes | Once after first deploy, and after every schema change |
| `seed_dynamodb.py` | Seeds 30 days of test sensor data into DynamoDB (prod-SensorEvents) | Once before first ETL run — gives the pipeline data to process |

## Deploy infrastructure (AWS)

Prerequisites:
- `infrastructure/terraform.tfvars` must exist (copy from `terraform.tfvars.example` and fill in your values)
- AWS credentials configured (`aws sts get-caller-identity` must succeed)

```bash
# From project root:
cd backend/project2a-behavior-analyzer

# 1. Deploy infrastructure (~5 min)
./scripts/deploy.sh prod

# 2. Run database migrations (once after first deploy)
python scripts/migrate.py
```

`deploy.sh` will:
1. Build Lambda packages into `dist/staging/`
2. Run `terraform init`
3. Run `terraform plan`
4. Run `terraform apply`

## Demo workflow

This project is deployed on-demand for demos only, to keep AWS costs near zero.

```bash
# Before demo (~10 min total)
./scripts/deploy.sh prod        # 1. provision infrastructure
python scripts/migrate.py       # 2. create database tables
python scripts/seed_dynamodb.py # 3. seed 30 days of test data into DynamoDB

# Then trigger the ETL via the API or the frontend Behavior Analyzer tab.

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
python scripts/seed_dynamodb.py
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
- Never run `seed_dynamodb.py` against production data
