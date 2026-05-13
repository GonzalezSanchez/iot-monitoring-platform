# Project 1a — Smart Room Monitor (Serverless Lambda)

## Overzicht

Serverless REST API voor real-time ingestie van sensor events (temperatuur, vochtigheid, bezetting, beweging) uit conferentieruimtes, met drempelwaarde-gebaseerde anomaliedetectie.

## Architectuur

```
API Gateway → Lambda handlers → DynamoDB
```

- **Runtime:** Python 3.12, AWS Lambda
- **Database:** DynamoDB (PAY_PER_REQUEST) — tabellen: prod-RoomStatus, prod-SensorEvents
- **Infrastructuur:** CloudFormation (volledig als code)
- **Structuur:** clean layered architecture — models → services → repositories
- **CI/CD:** GitHub Actions — tests + deploy op elke merge naar main

## API-endpoints

- `GET /rooms` — lijst van alle ruimtes met sensor status
- `GET /rooms/{room_id}` — details van één ruimte
- `POST /events` — nieuw sensor event toevoegen

## Deployment

Volledig via GitHub Actions:
```bash
# Lokaal deployen (indien nodig)
cd backend/project1a-smart-room-monitor
aws cloudformation deploy --template-file infrastructure/cloudformation.yaml \
  --stack-name smart-room-monitor --capabilities CAPABILITY_IAM
```

API live op: `https://6c20a9bn61.execute-api.eu-central-1.amazonaws.com/dev/`

## Verschillen t.o.v. project 1b

| | Project 1a | Project 1b |
|---|---|---|
| **Runtime** | AWS Lambda (event-driven) | FastAPI (altijd draaiend) |
| **Hosting** | AWS managed | Docker op home server |
| **Infrastructuur** | CloudFormation | Docker Compose |
| **Observability** | CloudWatch Logs | OTel → Datadog APM |
| **Kosten** | Pay per request | Vaste serverkosten |

Dezelfde domeinlogica — bewust twee keer gebouwd om scheiding van businesslogica en infrastructuur te demonstreren.

## Tests

105 tests, 84% coverage. Inclusief mypy type checking en ruff linting via CI.

## Toekomstige uitbreidingen

Zie `temp/uitbreidingen.md` — Project 1a: CloudWatch alarms.
