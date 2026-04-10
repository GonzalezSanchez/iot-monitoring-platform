# Scripts — Smart Room Monitor (Project 1)

Utility scripts for local development, testing, and demo data management.

---

## Overview

| Script | Purpose | When to use |
|--------|---------|-------------|
| `build.sh` | Build Lambda deployment package (deps to `dist/`, never `src/`) | Before deploying to AWS |
| `add_test_room.py` | Insert a demo room directly into DynamoDB | Once, after deploying infrastructure |
| `sensor_simulator.py` | Simulate IoT sensors sending events to the API | Local development and demos |
| `test-lambda-local.sh` | Invoke a Lambda handler locally in Docker | Local development with LocalStack |
| `view-logs.sh` | View logs from local Docker containers | Debugging local environment |

---

## Execution Order (first-time setup)

1. **`build.sh`** — build the Lambda deployment package
2. **Deploy infrastructure** (CloudFormation stack) — creates DynamoDB tables and Lambda functions
3. **`add_test_room.py`** — seed initial room data so the dashboard is not empty
4. **`sensor_simulator.py`** — send live events to demonstrate the full pipeline

---

## Scripts

### `build.sh`

Builds the Lambda deployment package. Installs dependencies into `dist/python/` (never into `src/`) and zips everything into `dist/lambda_package.zip`.

```bash
cd backend/project1a-smart-room-monitor
./scripts/build.sh
```

---

### `add_test_room.py`

Inserts a demo room directly into the `prod-RoomStatus` DynamoDB table.
Use this once after deploying to seed initial data.

**Prerequisites:** AWS credentials configured (`aws configure` or environment variables)

```bash
cd backend/project1a-smart-room-monitor
python scripts/add_test_room.py
```

---

### `sensor_simulator.py`

Simulates IoT sensors by sending random (but realistic) sensor events to the API
at a configurable interval. Useful for demonstrating the anomaly detection pipeline.

**Prerequisites:** API must be running (local or deployed)

```bash
# Against local API (LocalStack)
python scripts/sensor_simulator.py --api-url http://localhost:8080

# Against deployed AWS API
python scripts/sensor_simulator.py --api-url https://<api-id>.execute-api.eu-north-1.amazonaws.com/dev
```

---

### `test-lambda-local.sh`

Invokes a Lambda handler directly inside a running Docker container.
Requires LocalStack to be running with the Lambda deployed.

**Prerequisites:** Docker running, LocalStack container up (`docker compose up`)

```bash
# Test get_rooms handler (default)
./scripts/test-lambda-local.sh

# Test specific handler with custom event file
./scripts/test-lambda-local.sh handlers.ingest_event.lambda_handler scripts/test-events/ingest-event.json
```

---

### `view-logs.sh`

Tails logs from local Docker containers for debugging.

```bash
# LocalStack logs
./scripts/view-logs.sh localstack

# Lambda container logs
./scripts/view-logs.sh lambda

# LocalStack Lambda runtime logs
./scripts/view-logs.sh lambda-runtime
```
