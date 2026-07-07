# Project 3b — Infrastructure

CloudFormation template for the AWS resources the device gateway needs:

| Resource | Name | Purpose |
|----------|------|---------|
| DynamoDB table | `p3-prod-Devices` | Registered devices: hashed API key, device type, status, last seen |
| IAM user | `iot-gateway-app` | Least-privilege credentials for the gateway container |
| IAM user | `iot-gateway-consumer` | Least-privilege credentials for the normalizer consumer |

Each user gets exactly the operations its service performs, nothing else:

- `iot-gateway-app` — `GetItem`/`PutItem`/`UpdateItem` on the Devices table
  (what `src/gateway/repository.py` does)
- `iot-gateway-consumer` — `PutItem` on `prod-SensorEvents`, `GetItem`/`PutItem`
  on `prod-RoomStatus` (what `src/consumer/writer.py` does). The contract
  tables are owned by project 1b's stack; this template only grants access.

The two users are deliberately separate: the gateway cannot touch the contract
tables, the consumer cannot touch Devices.

## Deploy

Deployment runs through GitHub Actions
([`deploy-project3-infra.yml`](../../../.github/workflows/deploy-project3-infra.yml)):

- automatically on a push to `main` that touches `infrastructure/**`, or
- manually via *Actions → Deploy Project 3 Infrastructure → Run workflow*.

The workflow deploys the stack `iot-gateway-prod` in `eu-central-1` and prints
the stack outputs. `--no-fail-on-empty-changeset` makes re-runs idempotent.

## Access keys (one-time, after first deploy)

CloudFormation intentionally does not create the access keys: the secret would
end up in stack outputs or workflow logs. Create them once from any machine with
admin AWS CLI access:

```bash
aws iam create-access-key --user-name iot-gateway-app
aws iam create-access-key --user-name iot-gateway-consumer
```

Put each key pair in its service's env file on the server (never in git,
`chmod 600`): `backend/project3b-iot-gateway/.env.prod` for the gateway,
`.env.consumer.prod` for the consumer. Rotate by creating a new key, updating
the env file, then deleting the old one:

```bash
aws iam delete-access-key --user-name iot-gateway-app --access-key-id <old-id>
```

## Destroy

```bash
# Access keys block user deletion — remove them first (both users)
for u in iot-gateway-app iot-gateway-consumer; do
  aws iam list-access-keys --user-name $u
  aws iam delete-access-key --user-name $u --access-key-id <id>
done

aws cloudformation delete-stack --stack-name iot-gateway-prod
aws cloudformation wait stack-delete-complete --stack-name iot-gateway-prod
```

Deleting the stack removes the Devices table and all registered devices.
