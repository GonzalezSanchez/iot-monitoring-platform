# Project 3b — Infrastructure

CloudFormation template for the AWS resources the device gateway needs:

| Resource | Name | Purpose |
|----------|------|---------|
| DynamoDB table | `p3-prod-Devices` | Registered devices: hashed API key, device type, status, last seen |
| IAM user | `iot-gateway-app` | Least-privilege credentials for the gateway container |

The IAM policy grants only `dynamodb:GetItem`, `dynamodb:PutItem` and
`dynamodb:UpdateItem` on the Devices table — exactly the operations
`src/gateway/repository.py` performs, nothing else.

## Deploy

Deployment runs through GitHub Actions
([`deploy-project3-infra.yml`](../../../.github/workflows/deploy-project3-infra.yml)):

- automatically on a push to `main` that touches `infrastructure/**`, or
- manually via *Actions → Deploy Project 3 Infrastructure → Run workflow*.

The workflow deploys the stack `iot-gateway-prod` in `eu-central-1` and prints
the stack outputs. `--no-fail-on-empty-changeset` makes re-runs idempotent.

## Access key (one-time, after first deploy)

CloudFormation intentionally does not create the access key: the secret would
end up in stack outputs or workflow logs. Create it once from any machine with
admin AWS CLI access:

```bash
aws iam create-access-key --user-name iot-gateway-app
```

Put the key pair in `backend/project3-iot-gateway/.env.prod` on the server
(never in git, `chmod 600`) and rotate by creating a new key, updating
`.env.prod`, then deleting the old one:

```bash
aws iam delete-access-key --user-name iot-gateway-app --access-key-id <old-id>
```

## Destroy

```bash
# Access keys block user deletion — remove them first
aws iam list-access-keys --user-name iot-gateway-app
aws iam delete-access-key --user-name iot-gateway-app --access-key-id <id>

aws cloudformation delete-stack --stack-name iot-gateway-prod
aws cloudformation wait stack-delete-complete --stack-name iot-gateway-prod
```

Deleting the stack removes the Devices table and all registered devices.
