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
**Tests:** 105 unit tests, 84% coverage (pytest + moto for DynamoDB mocking)
**Auth:** Intentionally excluded — device authentication is covered in Project 3

[View project](backend/project1a-smart-room-monitor/)

---

### Project 1b — Smart Room Monitor (FastAPI + Docker)

Same domain logic as Project 1, re-implemented with FastAPI and deployed as a
containerised application. A deliberate choice to show infrastructure independence.

**Stack:** Python, FastAPI, DynamoDB (AWS), Docker, nginx, Cloudflare tunnel
**Live:** [iot.gonzalezsanchez.dev](https://iot.gonzalezsanchez.dev)
**API docs:** [iot.gonzalezsanchez.dev/docs](https://iot.gonzalezsanchez.dev/docs)
**Auth:** Intentionally excluded — device authentication (JWT via Cognito) is covered in Project 3

[View project](backend/project1b-smart-room-monitor-fastapi/)

---

### Project 2a — Behavior Pattern Analyzer (AWS native)

ETL pipeline that reads historical sensor data from Project 1a (DynamoDB) and detects
behavioral patterns across rooms over time — occupancy schedules, temperature trends,
unusual activity. Scheduled batch processing via EventBridge + Step Functions, results
stored in Aurora Serverless v2 and exposed via REST API.

**Stack:** Python 3.13, AWS Lambda, Step Functions, EventBridge, Aurora Serverless v2, Terraform, Docker
**Infrastructure:** Provisioned via Terraform (VPC, Aurora, IAM, Secrets Manager)
**CI:** GitHub Actions — mypy, ruff, pytest (unit + integration + regression), terraform validate
**Deploy:** On-demand for demos — destroyed after to minimise costs
**Tests:** Unit (mocked AWS), integration (real PostgreSQL via Docker), regression (documented production bugs)

[View project](backend/project2a-behavior-analyzer/)

---

### Project 2b — Behavior Pattern Analyzer (Data Engineering stack) *(planned)*

Same analytics goal as Project 2a, re-implemented with a data engineering stack.
A deliberate choice to demonstrate the same problem solved with different tools.

**Stack:** Python, Apache Airflow, PySpark, RDS PostgreSQL, Power BI
**CI/CD:** GitHub Actions (CI) + Jenkins (CD) — deployment pipeline with environment promotion (dev → staging → prod)

---

### Project 3 — IoT Device Gateway Simulator *(planned)*

Secure gateway for IoT device registration, authentication, and rate limiting.
Simulates how a production IoT platform manages devices — registration,
command & control, reliable message delivery, and device status monitoring.

**AWS variant (3a):** API Gateway, Lambda, Cognito, DynamoDB, SQS
**FastAPI variant (3b):** FastAPI, API key auth (hashed, validated via Depends()), Docker

---

### Project 4 — LLM / MCP Layer *(planned)*

AI integration layer on top of the existing platform. Exposes the FastAPI routes as MCP
tools via `fastapi-mcp`, enabling natural language queries over live sensor data.

*"Which rooms had anomalies this week?" → Claude queries the IoT platform directly.*

**Stack:** Python, fastapi-mcp, Claude API (Anthropic), RAG, Docker

---

### Frontend — React Dashboard

Real-time dashboard for visualising sensor data and room states.

**Stack:** React, TanStack Query, Vite, nginx
**Live:** [iot.gonzalezsanchez.dev](https://iot.gonzalezsanchez.dev)

---

## Skills Demonstrated

| Skill | Where |
|-------|-------|
| Python clean architecture (models → services → repositories) | project 1, 1b, 2a |
| RESTful API design | project 1 (Lambda handlers), 1b (FastAPI), 2a |
| AWS serverless (Lambda, API Gateway, CloudWatch) | project 1, 2a |
| DynamoDB data modelling | project 1, 1b |
| ETL pipeline design (Extract → Transform → Analyze) | project 2a |
| Step Functions orchestration | project 2a |
| Aurora Serverless v2 + PostgreSQL schema design | project 2a |
| Idempotent writes (ON CONFLICT DO NOTHING/UPDATE) | project 2a |
| Regression testing (documented production bugs) | project 2a |
| Infrastructure as Code (CloudFormation) | project 1 |
| Infrastructure as Code (Terraform) | project 2a |
| Docker + nginx | project 1b, frontend |
| CI/CD with GitHub Actions | project 1, 1b, 2a |
| Pydantic v2 models + validation | project 1, 1b, 2a |
| Anomaly detection logic | project 1, 1b, 2a |
| pytest + moto (DynamoDB mocking), 80%+ coverage | project 1, 1b, 2a |
| mypy + pre-commit hooks | project 1, 1b, 2a |
| Cloudflare tunnel + production deployment | project 1b |

---

## Repository Structure

```
iot-monitoring-platform/
├── backend/
│   ├── project1a-smart-room-monitor/          # AWS Lambda + API Gateway (live)
│   ├── project1b-smart-room-monitor-fastapi/ # FastAPI + Docker (live)
│   ├── project2a-behavior-analyzer/          # AWS native ETL pipeline (complete)
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
