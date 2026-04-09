#!/usr/bin/env bash
# Destroy all project 2a infrastructure using Terraform.
# Usage: ./scripts/destroy.sh [dev|prod]
#
# WARNING: This deletes ALL infrastructure including the Aurora database.
# Only use this after a demo to avoid ongoing AWS costs (~$15/month).

set -e

ENV=${1:-prod}

echo "WARNING: This will destroy ALL p2a infrastructure for environment: ${ENV}"
echo "This includes the Aurora database and all VPC resources."
echo ""
read -rp "Type '${ENV}' to confirm: " CONFIRM

if [[ "${CONFIRM}" != "${ENV}" ]]; then
  echo "Aborted."
  exit 1
fi

cd infrastructure

echo "Destroying project 2a infrastructure..."
terraform destroy -var-file=terraform.tfvars -auto-approve

echo ""
echo "All infrastructure destroyed. AWS costs stopped."
echo "Re-deploy with: ./scripts/deploy.sh ${ENV}"
