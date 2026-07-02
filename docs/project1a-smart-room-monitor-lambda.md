# Project 1a — Smart Room Monitor (Serverless Lambda)

## Overview

Serverless REST API for real-time ingestion of sensor events (temperature, humidity, occupancy, motion) from conference rooms, with threshold-based anomaly detection.

## Architecture

```
API Gateway → Lambda handlers → DynamoDB
```

- **Runtime:** Python 3.12, AWS Lambda
- **Database:** DynamoDB (PAY_PER_REQUEST) — tables: prod-RoomStatus, prod-SensorEvents
- **Infrastructure:** CloudFormation (fully as code)
- **Structure:** clean layered architecture — models → services → repositories
- **CI/CD:** GitHub Actions — tests + deploy on every merge to main

## API Endpoints

- `GET /rooms` — list of all rooms with sensor status
- `GET /rooms/{room_id}` — details of a single room
- `POST /events` — add a new sensor event

## Deployment

Fully via GitHub Actions:
```bash
# Deploy locally (if needed)
cd backend/project1a-smart-room-monitor
aws cloudformation deploy --template-file infrastructure/cloudformation.yaml \
  --stack-name smart-room-monitor --capabilities CAPABILITY_IAM
```

API live at: `https://6c20a9bn61.execute-api.eu-central-1.amazonaws.com/dev/`

## Differences from project 1b

| | Project 1a | Project 1b |
|---|---|---|
| **Runtime** | AWS Lambda (event-driven) | FastAPI (always running) |
| **Hosting** | AWS managed | Docker on home server |
| **Infrastructure** | CloudFormation | Docker Compose |
| **Observability** | CloudWatch Logs | OTel → Datadog APM |
| **Cost** | Pay per request | Fixed server costs |

Same domain logic — deliberately built twice to demonstrate the separation of business logic and infrastructure.

## Tests

105 tests, 84% coverage. Includes mypy type checking and ruff linting via CI.

## Future extensions

See `temp/uitbreidingen.md` — Project 1a: CloudWatch alarms.
