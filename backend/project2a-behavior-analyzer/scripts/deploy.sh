#!/usr/bin/env bash
# Deploy CloudFormation stacks for project 2a in the correct order.
# Usage: ./deploy.sh [dev|prod]

set -e

ENV=${1:-prod}
REGION=eu-central-1
STACK_PREFIX="p2a-${ENV}"

echo "Deploying project 2a infrastructure — environment: ${ENV}"
echo "Region: ${REGION}"
echo "---"

# Ask for the DynamoDB SensorEvents table ARN (from project 1a output)
read -rp "Enter ARN of project 1a SensorEvents DynamoDB table: " DYNAMO_ARN

if [[ -z "${DYNAMO_ARN}" ]]; then
  echo "ERROR: DynamoDB table ARN cannot be empty."
  exit 1
fi

# 1. VPC + networking
echo "[1/4] Deploying VPC stack..."
aws cloudformation deploy \
  --template-file infrastructure/vpc.yml \
  --stack-name "${STACK_PREFIX}-vpc" \
  --parameter-overrides Environment="${ENV}" \
  --region "${REGION}" \
  --no-fail-on-empty-changeset

# 2. Aurora Serverless v2
echo "[2/4] Deploying Aurora database stack..."
aws cloudformation deploy \
  --template-file infrastructure/database.yml \
  --stack-name "${STACK_PREFIX}-database" \
  --parameter-overrides Environment="${ENV}" \
  --region "${REGION}" \
  --no-fail-on-empty-changeset

# 3. IAM roles
echo "[3/4] Deploying IAM stack..."
aws cloudformation deploy \
  --template-file infrastructure/iam.yml \
  --stack-name "${STACK_PREFIX}-iam" \
  --parameter-overrides \
      Environment="${ENV}" \
      SourceDynamoDBTableArn="${DYNAMO_ARN}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "${REGION}" \
  --no-fail-on-empty-changeset

# 4. Secrets Manager
echo "[4/4] Deploying Secrets stack..."
aws cloudformation deploy \
  --template-file infrastructure/secrets.yml \
  --stack-name "${STACK_PREFIX}-secrets" \
  --parameter-overrides Environment="${ENV}" \
  --region "${REGION}" \
  --no-fail-on-empty-changeset

# Fetch the Aurora endpoint and update the secret
echo ""
echo "Fetching Aurora endpoint to update secret..."
AURORA_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_PREFIX}-database" \
  --region "${REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='AuroraClusterEndpoint'].OutputValue" \
  --output text)

echo "Aurora endpoint: ${AURORA_ENDPOINT}"
echo ""
echo "ACTION REQUIRED: Update the secret p2a-${ENV}-db-credentials with the real password."
echo "Run:"
echo "  aws secretsmanager update-secret \\"
echo "    --secret-id p2a-${ENV}-db-credentials \\"
echo "    --secret-string '{\"host\":\"${AURORA_ENDPOINT}\",\"port\":5432,\"dbname\":\"p2a_prod\",\"username\":\"p2admin\",\"password\":\"<your-password>\"}'"
echo ""
echo "All stacks deployed successfully."
