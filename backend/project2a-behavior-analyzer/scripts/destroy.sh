#!/usr/bin/env bash
# Tear down all CloudFormation stacks for project 2a in reverse order.
# Usage: ./destroy.sh [dev|prod]

set -e

ENV=${1:-prod}
REGION=eu-central-1
STACK_PREFIX="p2a-${ENV}"

echo "WARNING: This will delete all p2a infrastructure for environment: ${ENV}"
read -rp "Are you sure? (yes/no): " CONFIRM
if [[ "${CONFIRM}" != "yes" ]]; then
  echo "Aborted."
  exit 0
fi

echo "Destroying project 2a infrastructure — environment: ${ENV}"
echo "---"

# Reverse order: secrets → iam → database → vpc

echo "[1/4] Deleting Secrets stack..."
aws cloudformation delete-stack \
  --stack-name "${STACK_PREFIX}-secrets" \
  --region "${REGION}"
aws cloudformation wait stack-delete-complete \
  --stack-name "${STACK_PREFIX}-secrets" \
  --region "${REGION}"

echo "[2/4] Deleting IAM stack..."
aws cloudformation delete-stack \
  --stack-name "${STACK_PREFIX}-iam" \
  --region "${REGION}"
aws cloudformation wait stack-delete-complete \
  --stack-name "${STACK_PREFIX}-iam" \
  --region "${REGION}"

echo "[3/4] Deleting Aurora database stack..."
aws cloudformation delete-stack \
  --stack-name "${STACK_PREFIX}-database" \
  --region "${REGION}"
aws cloudformation wait stack-delete-complete \
  --stack-name "${STACK_PREFIX}-database" \
  --region "${REGION}"

echo "[4/4] Deleting VPC stack..."
aws cloudformation delete-stack \
  --stack-name "${STACK_PREFIX}-vpc" \
  --region "${REGION}"
aws cloudformation wait stack-delete-complete \
  --stack-name "${STACK_PREFIX}-vpc" \
  --region "${REGION}"

echo "All stacks deleted. You are no longer being charged."
