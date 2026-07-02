# Project 1b — Smart Room Monitor (FastAPI)

## Overview
This document describes the FastAPI version of the Smart Room Monitor backend (project1b). It explains the architecture, technologies used, endpoints, and migration from the original Lambda implementation.

## Contents
- Purpose and scope
- Architecture overview
- Differences from the Lambda version
- API endpoints
- Reused code
- Installation and startup
- Future extensions

## 1. Purpose and scope
This backend provides a REST API for monitoring rooms and sensor data, as an alternative to the serverless Lambda solution.

## 2. Architecture overview
- **Framework:** FastAPI
- **Database:** DynamoDB (via boto3)
- **Structure:** models/, repositories/, services/, utils/
- **API:** REST endpoints for rooms and events

## 3. Differences from the Lambda version
- No AWS Lambda, but a dedicated FastAPI server
- Easier to test and extend locally
- Responsible for its own hosting and scaling

## 4. API endpoints (example)
- `GET /rooms` — list of all rooms
- `GET /rooms/{room_id}` — details of a single room
- `POST /events` — add a new event

## 5. Reused code
- Models, repositories, and services mostly carried over from project1
- Adjustments for FastAPI routing and dependency injection

## 6. Installation and startup
```bash
cd backend/project1b-smart-room-monitor-fastapi
pip install -r requirements.txt
uvicorn main:app --reload
```

## 7. Observability

Vendor-neutral observability pipeline via OpenTelemetry:

```
FastAPI (opentelemetry-instrument uvicorn)
  → OTLP gRPC → OTel Collector → Datadog (datadoghq.eu)
```

- **Auto-instrumentation:** `opentelemetry-instrument` wraps uvicorn — no code changes in `main.py`
- **Traces:** every HTTP request + DynamoDB calls as child spans
- **Metrics:** request latency, throughput, error rate
- **Logs:** trace ID correlation via `OTEL_PYTHON_LOG_CORRELATION=true`
- **Vendor-neutral:** backend sends OTLP, only the Collector config changes when switching to Grafana Stack

See `temp/stappen_observability_project1b.md` for the full implementation.

## 8. Future extensions
- Authentication/authorization (JWT via Cognito — see Project 3)
- More endpoints (e.g. for sensors)
- Switch observability to Grafana Stack (Tempo + Loki + Prometheus) after the Datadog trial
- Expand docs: OTel/Datadog setup, nginx reverse proxy, docker-compose production architecture
- Short operations section: redeploy procedure, Cloudflare tunnel recovery
