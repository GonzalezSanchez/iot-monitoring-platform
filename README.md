![CI](https://github.com/GonzalezSanchez/iot-monitoring-platform/actions/workflows/ci.yml/badge.svg)

# IoT Monitoring Platform

Portfolio project demonstrating backend engineering skills in an IoT context.

The platform ingests sensor data from conference rooms (temperature, humidity, occupancy, motion), runs anomaly detection, and tracks room state in real time.

**Live demo:** [iot.gonzalezsanchez.dev](https://iot.gonzalezsanchez.dev)
**API docs:** [iot.gonzalezsanchez.dev/docs](https://iot.gonzalezsanchez.dev/docs)
**Developer:** Álvaro González Sánchez — [gonzalezsanchez.dev](https://gonzalezsanchez.dev) | [LinkedIn](https://www.linkedin.com/in/GonzalezSanchez)

---

## Architecture

```
IoT Sensor / API Client
        │
        ▼
 API Gateway (REST)
        │
   ┌────┴────────────────┐
   │                     │
   ▼                     ▼
POST /events          GET /rooms
(ingest_event)        (get_rooms / get_room_detail)
   │                     │
   ▼                     ▼
EventService         RoomRepository
   │
   ├── AnomalyDetector (threshold checks)
   ├── EventRepository (DynamoDB)
   └── RoomRepository  (DynamoDB — state update)

DynamoDB
├── SensorEvents  (room_id + timestamp)
└── RoomStatus    (room_id)
```

---

## Platform Architecture

A real IoT system has three distinct layers. This platform covers all three:

| Layer | Responsibility | Project |
|-------|---------------|---------|
| **Device layer** | How devices authenticate and send data securely | Project 3 |
| **Ingestion layer** | How sensor events are processed and stored | Project 1 / 1b |
| **Analytics layer** | What patterns emerge from the data over time | Project 2a / 2b |

Projects 1 and 2 are each implemented twice — deliberately — to demonstrate that the same business logic can be solved with different infrastructure choices.

---

## Projects

### Project 1 — Smart Room Monitor (AWS Lambda + API Gateway)

Serverless REST API deployed to AWS. Sensor events are ingested via API Gateway,
processed through anomaly detection, and stored in DynamoDB.

**Stack:** Python, AWS Lambda, API Gateway, DynamoDB, CloudFormation, CloudWatch
**Infrastructure:** Provisioned via CloudFormation (tables + IAM — least-privilege)
**CI/CD:** GitHub Actions — tests on every push, deploy to AWS on merge to main
**Tests:** 108 unit tests, 82% coverage (pytest + moto for DynamoDB mocking)

[View project](backend/project1a-smart-room-monitor/)

---

### Project 1b — Smart Room Monitor (FastAPI + Docker)

Same domain logic as Project 1, re-implemented with FastAPI and deployed as a
containerised application. A deliberate choice to show infrastructure independence.

**Stack:** Python, FastAPI, DynamoDB (AWS), Docker, nginx, Cloudflare tunnel
**Live:** [iot.gonzalezsanchez.dev](https://iot.gonzalezsanchez.dev)
**API docs:** [iot.gonzalezsanchez.dev/docs](https://iot.gonzalezsanchez.dev/docs)

[View project](backend/project1b-smart-room-monitor-fastapi/)

---

### Project 2a — Behavior Pattern Analyzer (AWS native) *(in progress)*

ETL pipeline that reads historical sensor data from Project 1a (DynamoDB) and detects
behavioral patterns across rooms over time — occupancy schedules, temperature trends,
unusual activity. Scheduled batch processing via EventBridge + Step Functions, results
stored in Aurora Serverless v2 and exposed via REST API.

**Stack:** Python, AWS Lambda, Step Functions, EventBridge, Aurora Serverless v2, CloudFormation, Docker
**Infrastructure:** Provisioned via CloudFormation (VPC, Aurora, IAM, Secrets Manager)
**Deploy:** On-demand for demos (`./scripts/deploy.sh`) — destroyed after to minimise costs

[View project](backend/project2a-behavior-analyzer/)

---

### Project 2b — Behavior Pattern Analyzer (Data Engineering stack) *(planned)*

Same analytics goal as Project 2a, re-implemented with a data engineering stack.
A deliberate choice to demonstrate the same problem solved with different tools.

**Stack:** Python, Apache Airflow, PySpark, RDS PostgreSQL, Power BI

---

### Project 3 — IoT Device Gateway Simulator *(planned)*

Secure gateway for IoT device registration, authentication (JWT via Cognito), and
rate limiting. Simulates how a production IoT platform manages devices — registration,
command & control, reliable message delivery via SQS, and device status monitoring.

**Stack:** Python, AWS API Gateway, Lambda, Cognito, DynamoDB, SQS, Docker

---

### Frontend — React Dashboard

Real-time dashboard for visualising sensor data and room states.

**Stack:** React, TanStack Query, Vite, nginx
**Live:** [iot.gonzalezsanchez.dev](https://iot.gonzalezsanchez.dev)

---

## Skills Demonstrated

| Skill | Where |
|-------|-------|
| Python clean architecture (models → services → repositories) | project 1, 1b |
| RESTful API design | project 1 (Lambda handlers), 1b (FastAPI) |
| AWS serverless (Lambda, API Gateway, CloudWatch) | project 1 |
| DynamoDB data modelling | project 1, 1b |
| Infrastructure as Code (CloudFormation) | project 1, 1b |
| Docker + multi-stage builds + nginx | project 1b, frontend |
| CI/CD with GitHub Actions | project 1, 1b |
| Pydantic v2 models + validation | project 1, 1b |
| Anomaly detection logic | project 1, 1b |
| pytest + moto (DynamoDB mocking), 82% coverage | project 1 |
| mypy + pre-commit hooks | project 1, 1b |
| Cloudflare tunnel + production deployment | project 1b |

---

## Repository Structure

```
iot-monitoring-platform/
├── backend/
│   ├── project1a-smart-room-monitor/          # AWS Lambda + API Gateway (live)
│   ├── project1b-smart-room-monitor-fastapi/ # FastAPI + Docker (live)
│   ├── project2a-behavior-analyzer/          # AWS native ETL pipeline (planned)
│   ├── project2b-behavior-analyzer/          # Airflow + PySpark (planned)
│   └── project3-iot-gateway/                 # Device gateway (planned)
├── docs/                                      # Project specs and architecture
├── frontend/                                  # React dashboard
├── docker-compose.prod.yml                    # Production deployment
└── .github/workflows/                         # CI + deploy pipelines
```

---

## Running Locally

```bash
# Backend (FastAPI)
cd backend/project1b-smart-room-monitor-fastapi
cp .env.example .env        # fill in your AWS credentials
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

---

© 2026 Álvaro González Sánchez. All rights reserved.
