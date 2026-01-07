# Portfolio Architectuur

## Overzicht

Dit portfolio bestaat uit 3 backend projecten en 1 frontend dashboard die samen een IoT monitoring en analytics platform vormen.

## Tech Stack

### Backend
- **Runtime:** Python 3.11+
- **Cloud:** AWS (Lambda, API Gateway, DynamoDB, RDS PostgreSQL, CloudWatch)
- **Containerization:** Docker
- **Testing:** pytest, unittest

### Frontend
- **Framework:** React 18+
- **State Management:** Zustand + TanStack Query (React Query)
- **Styling:** TailwindCSS
- **Charts:** Chart.js / Recharts

## Systeem Architectuur

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend Dashboard                      │
│                    (React + TanStack Query)                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   Project 1  │ │   Project 2  │ │   Project 3  │
│Smart Room    │ │Behavior      │ │IoT Gateway   │
│Monitor       │ │Analyzer      │ │Simulator     │
└──────────────┘ └──────────────┘ └──────────────┘
```

## Design Principles

### Clean Architecture
- Domain layer (models, business logic)
- Application layer (use cases, services)
- Infrastructure layer (repositories, external services)

### Event-Driven Design
- Asynchronous processing waar mogelijk
- Event sourcing voor auditability
- Message queues voor decoupling

### Security First
- JWT authentication
- Input validation
- Rate limiting
- Secure secrets management

## Deployment

Alle projecten zijn containerized met Docker en deployable naar AWS:
- **Lambda:** Python functions
- **API Gateway:** REST endpoints
- **DynamoDB/RDS:** Data persistence
- **CloudWatch:** Monitoring & logging

## Zie Ook

- [Project 1: Smart Room Monitor](project1-smart-room-monitor.md)
- [Project 2: Behavior Analyzer](project2-behavior-analyzer.md)
- [Project 3: IoT Gateway](project3-iot-gateway.md)
