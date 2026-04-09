#!/usr/bin/env bash
# Deploy project 2a infrastructure using Terraform.
# Usage: ./scripts/deploy.sh [dev|prod]

set -e

ENV=${1:-prod}
TFVARS="infrastructure/terraform.tfvars"

echo "Deploying project 2a infrastructure — environment: ${ENV}"
echo "---"

# Create terraform.tfvars if it doesn't exist
if [[ ! -f "${TFVARS}" ]]; then
  read -rp "Enter ARN of project 1a SensorEvents DynamoDB table: " DYNAMO_ARN

  if [[ -z "${DYNAMO_ARN}" ]]; then
    echo "ERROR: DynamoDB table ARN cannot be empty."
    exit 1
  fi

  cat > "${TFVARS}" << EOF
environment               = "${ENV}"
region                    = "eu-central-1"
source_dynamodb_table_arn = "${DYNAMO_ARN}"
EOF
  echo "Created ${TFVARS}"
fi

cd infrastructure

echo "[1/3] Initialising Terraform..."
terraform init

echo "[2/3] Planning..."
terraform plan -var-file=terraform.tfvars

echo "[3/3] Applying..."
terraform apply -var-file=terraform.tfvars -auto-approve

echo ""
echo "Done. Aurora endpoint:"
terraform output aurora_endpoint
echo ""
echo "All infrastructure deployed successfully."
