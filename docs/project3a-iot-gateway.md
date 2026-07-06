# Project 3a — IoT Device Gateway (AWS-native variant)

> **Status: specced only — not built.** Project 3 is implemented as
> [3b (FastAPI + Kafka)](project3b-iot-gateway.md); this document records the
> AWS-native design for comparison, mirroring how projects 1a/1b and 2a/2b pair
> a managed-AWS variant with a self-hosted one. Build contract and variant
> rationale: [project3-prd.md](project3-prd.md).

Secure gateway for IoT device registration, authentication, and message
delivery — the device layer of the platform, built entirely on managed AWS
services with a deploy/destroy lifecycle like project 2a.

## Tech Stack

- **Runtime:** Python 3.12
- **Cloud Services:** AWS API Gateway, Lambda, Cognito, DynamoDB, SQS
- **Containerization:** Docker (LocalStack for local development)
- **Testing:** pytest

## Architecture

```
IoT Device (sensor)
        │
        ▼
API Gateway (HTTP) — JWT auth via Cognito authorizer
        │
        ├── POST /devices/register     → RegisterDevice Lambda
        ├── POST /devices/{id}/auth    → AuthDevice Lambda (issues JWT)
        ├── POST /messages             → IngestMessage Lambda → SQS → ProcessMessage Lambda
        ├── POST /commands/{id}        → SendCommand Lambda → SQS (command queue)
        └── GET  /devices/{id}/status  → GetDeviceStatus Lambda
                │
                ▼
          DynamoDB
          ├── Devices table
          ├── Messages table
          └── RateLimits table
```

The API contract (endpoints, request/response shapes) is shared with 3b — see
the [API section of the 3b spec](project3b-iot-gateway.md#api-endpoints).

## Key Design Decisions

**Cognito for JWT** — device authentication uses AWS Cognito User Pools. Devices
register once, receive credentials, and exchange them for short-lived JWTs. API
Gateway validates the JWT on every request via a Cognito authorizer — no custom
auth logic in Lambda.

**SQS for reliable delivery** — messages are queued in SQS before processing.
If the processor Lambda fails, the message stays in the queue and retries automatically.
After max retries, messages go to a Dead Letter Queue (DLQ) for inspection.

**Rate limiting via DynamoDB** — per-device request counts are tracked in a
`RateLimits` table with a TTL-based sliding window. Checked in the IngestMessage
Lambda before queuing. Default: 1000 messages/hour per device, configurable per
device type; exceeded limit → 429 Too Many Requests.

**Deploy/destroy strategy** — same as project 2a. Deploy for demos, destroy after
to minimise costs.

## DynamoDB Schema

**Devices table** (`p3-{env}-Devices`):
- PK: `device_id` (String)
- Attributes: `device_type`, `api_key_hash`, `cognito_username`, `status` (registered/online/offline/suspended), `metadata` (Map), `registered_at`, `last_seen`

**Messages table** (`p3-{env}-Messages`):
- PK: `device_id` (String)
- SK: `timestamp` (String)
- Attributes: `message_id`, `payload` (Map), `status` (queued/processed/failed), `sqs_message_id`

**RateLimits table** (`p3-{env}-RateLimits`):
- PK: `device_id` (String)
- SK: `window` (String — hourly bucket e.g. `2026-01-07T10`)
- Attributes: `request_count` (Number), `limit` (Number), `ttl` (Number — epoch for DynamoDB TTL auto-cleanup)

## Infrastructure

Provisioned via CloudFormation:

| File | What it creates |
|---|---|
| `cognito.yml` | Cognito User Pool + App Client for device auth |
| `dynamodb.yml` | Devices, Messages, RateLimits tables |
| `sqs.yml` | Message queue + Command queue + DLQs |
| `lambdas.yml` | 5 Lambda functions + IAM roles |
| `apigateway.yml` | HTTP API + Cognito authorizer + routes |

## Security

- JWT validation via Cognito authorizer on API Gateway — no auth logic in Lambda
- API keys stored as bcrypt hashes in DynamoDB — never in plaintext
- Input validation via Pydantic on all Lambda handlers
- TLS in transit (API Gateway enforced), encryption at rest (DynamoDB default)
- Least-privilege IAM: each Lambda has its own role with only the permissions it needs

## Planned Project Structure

```
project3a-iot-gateway/
├── src/
│   ├── handlers/          # Lambda entry points
│   │   ├── register_device.py
│   │   ├── auth_device.py
│   │   ├── ingest_message.py
│   │   ├── process_message.py
│   │   ├── send_command.py
│   │   └── get_device_status.py
│   ├── models/            # Pydantic models
│   ├── repositories/      # DynamoDB access
│   ├── services/          # Business logic (auth, rate limiting)
│   └── utils/             # Response helpers
├── infrastructure/
│   ├── cognito.yml
│   ├── dynamodb.yml
│   ├── sqs.yml
│   ├── lambdas.yml
│   └── apigateway.yml
├── scripts/
│   ├── deploy.sh
│   ├── destroy.sh
│   └── simulate_device.py
├── tests/
│   ├── unit/              # moto — no Docker needed
│   └── integration/       # requires LocalStack
├── docker/
│   └── docker-compose.yml # LocalStack (DynamoDB + SQS + Cognito simulation)
├── config/
│   └── rate_limits.yml
├── requirements.txt
├── requirements-dev.txt
└── README.md
```
