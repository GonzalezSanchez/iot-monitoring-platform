![CI](https://github.com/GonzalezSanchez/iot-monitoring-platform/actions/workflows/ci.yml/badge.svg)

# IoT Monitoring Platform

Portfolio project demonstrating backend development skills in an IoT context.

The platform ingests sensor data from conference rooms (temperature, humidity, occupancy, motion), runs anomaly detection, and tracks room state in real time.

**Developer:** Álvaro González Sánchez
**Contact:** a.gonzalez.sanchez@gmail.com | [LinkedIn](https://www.linkedin.com/in/GonzalezSanchez)

---

## Projects

### Project 1 — Smart Room Monitor (AWS Lambda)

Serverless implementation of the monitoring API.

**Stack:** AWS Lambda, API Gateway, DynamoDB, CloudWatch, Python, Docker
**Status:** Complete — tested against AWS (production-like environment)

[View project](backend/project1-smart-room-monitor/)

---

### Project 1b — Smart Room Monitor (FastAPI)

Same domain logic, locally-runnable with Docker. No AWS account required.

**Stack:** FastAPI, DynamoDB Local, Docker, Python, pytest + moto
**Status:** Complete — 12/12 tests passing

Demonstrates the same clean architecture (models → services → repositories) with a FastAPI transport layer instead of Lambda handlers.

[View project](backend/project1b-smart-room-monitor-fastapi/)

---

### Project 2 — Behavior Pattern Analyzer *(planned)*

ETL pipeline for detecting behavioral patterns and anomalies across rooms over time.

**Stack:** AWS Lambda, RDS PostgreSQL, Step Functions, Python

---

### Project 3 — IoT Device Gateway *(planned)*

Secure gateway for IoT device registration, authentication, and rate limiting.

**Stack:** API Gateway, Cognito, DynamoDB, SQS, Python

---

### Frontend — React Dashboard

Real-time dashboard for visualising sensor data and room states.

**Stack:** React, TanStack Query, Zustand, Chart.js, TailwindCSS
**Status:** Mockup complete — connected to project 1b FastAPI backend

---

## Skills Demonstrated

| Skill | Where |
|-------|-------|
| Python OOP, clean architecture | project 1, 1b |
| RESTful API design | project 1 (Lambda), 1b (FastAPI) |
| DynamoDB data modelling | project 1, 1b |
| Pydantic v2 models + validation | project 1b |
| Anomaly detection logic | project 1, 1b |
| pytest + moto (AWS mocking), 91% coverage | project 1b |
| Docker containerisation | project 1, 1b |
| mypy + pre-commit type checking | project 1b |
| IoT sensor simulation | project 1, 1b |

---

## Repository Structure

```
iot-monitoring-platform/
├── backend/
│   ├── project1-smart-room-monitor/          # AWS Lambda
│   └── project1b-smart-room-monitor-fastapi/ # FastAPI (local)
├── frontend/                                  # React dashboard
└── docs/                                      # Architecture docs
```

---

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Project 1: Smart Room Monitor](docs/project1-smart-room-monitor.md)

---

© 2026 Álvaro González Sánchez. All rights reserved.
