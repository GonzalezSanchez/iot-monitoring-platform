# Scripts

## Overview

| Script | Purpose | When to run |
|--------|---------|-------------|
| `build.sh` | Packages Lambda source files into `dist/staging/` | Automatically called by `deploy.sh` |
| `deploy.sh` | Builds packages + runs `terraform init/plan/apply` | Before a demo or when infrastructure changes are needed |
| `destroy.sh` | Runs `terraform destroy` to tear down all resources | After a demo to stop AWS costs (~$15/month) |
| `migrate.py` | Creates/updates all database tables and indexes | Once after first deploy, and after every schema change |
| `seed_dynamodb.py` | Seeds 30 days of test sensor data into DynamoDB (prod-SensorEvents) | Once before first ETL run — gives the pipeline data to process |
| `seed_rooms.py` | Seeds 3 rooms with building names and coordinates into Aurora | Once after migrate.py |

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
aws lambda invoke --function-name p2a-prod-migrate \
  --region eu-central-1 --log-type Tail /tmp/migrate-output.json
cat /tmp/migrate-output.json
# Expected: {"status": "ok", "statements_executed": 9}
```

`deploy.sh` will:
1. Build Lambda packages into `dist/staging/`
2. Run `terraform init`
3. Run `terraform plan`
4. Run `terraform apply`

> **Why a Lambda for migrations?** Aurora runs in a private VPC — no public access.
> The migrate Lambda runs inside the VPC and can reach Aurora directly.
> `scripts/migrate.py` is kept for local development only (connects via `.env`).

## Demo workflow

This project is deployed on-demand for demos only, to keep AWS costs near zero.

```bash
# Before demo (~10 min total)
./scripts/deploy.sh prod        # 1. provision infrastructure

# 2. create database tables (Lambda runs inside VPC, reaches Aurora)
aws lambda invoke --function-name p2a-prod-migrate \
  --region eu-central-1 --log-type Tail /tmp/migrate-output.json
cat /tmp/migrate-output.json    # expected: {"status": "ok", ...}

python scripts/seed_dynamodb.py # 3. seed 30 days of test data into DynamoDB

# 4. Get the API Gateway URL and update the frontend
terraform -chdir=infrastructure output -raw api_gateway_url
# → copy this URL into frontend/.env:
#   VITE_P2A_API_ENDPOINT=https://<id>.execute-api.eu-central-1.amazonaws.com
# Note: this URL changes every time you destroy + redeploy

# Then trigger the ETL via the API or the frontend Behavior Analyzer tab.

# After demo: destroy everything to stop costs
# ⚠️  BEFORE running destroy, disable deletion protection first:
#   In infrastructure/database.tf, change:
#     deletion_protection = var.environment == "prod"
#   to:
#     deletion_protection = false
#   Then: terraform apply -var-file=terraform.tfvars -target=aws_rds_cluster.aurora -auto-approve
#   Then run destroy. Revert database.tf afterwards (do NOT commit the change).
./scripts/destroy.sh prod

# ⚠️  AFTER destroy: delete the GitHub secret to show "not deployed" in the frontend
#   GitHub → Settings → Secrets → Actions → VITE_P2A_API_ENDPOINT → Delete
#   (do NOT set to empty string — GitHub ignores empty secrets, old value stays baked in)
#   Then trigger a rebuild: git commit --allow-empty -m "chore: rebuild frontend — p2a not deployed" && git push origin main
#   On the server: docker compose -f docker-compose.prod.yml pull && docker compose -f docker-compose.prod.yml up -d
```

Estimated cost while deployed: ~$15/month (VPC endpoints ~$14, Aurora serverless ~$1 when idle).

## Local development

For a fresh local setup:

```bash
# 1. Start local PostgreSQL
docker compose -f docker/docker-compose.yml up -d

# 2. Create tables
python scripts/migrate.py

# 3. Seed rooms with building names and coordinates
python scripts/seed_rooms.py

# 4. (Optional) seed sensor test data
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

## After redeploy: update GitHub secret and frontend

The API Gateway URL changes every `destroy` + `deploy`. After each redeploy:

```bash
# 1. Get the new URL
terraform -chdir=infrastructure output -raw api_gateway_url
```

Then update **two places**:

**GitHub secret** (used by CI to bake the URL into the Docker image):
- Go to GitHub → Settings → Secrets → Actions
- Create or update `VITE_P2A_API_ENDPOINT` with the new URL
- Note: setting to empty string does NOT work — delete the secret instead when not deployed
- Trigger a new Docker build: `git commit --allow-empty -m "chore: rebuild frontend image" && git push`
- On the server: `docker compose -f docker-compose.prod.yml pull && docker compose -f docker-compose.prod.yml up -d`

**Local `.env`** (for local development):
- Update `VITE_P2A_API_ENDPOINT` in `frontend/.env`

## Notes

- `migrate.py` is idempotent — safe to run multiple times (`CREATE TABLE IF NOT EXISTS`)
- In production (AWS): `migrate.py` runs once manually after infrastructure is provisioned
- Never run `seed_dynamodb.py` against production data
