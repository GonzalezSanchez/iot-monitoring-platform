
Laatste update: 15 januari 2026

© 2026 Álvaro González Sánchez. Alle rechten voorbehouden. Gebruik of verspreiding zonder toestemming is niet toegestaan.

# Backend Developer Portfolio

**Ontwikkelaar:** Álvaro González Sánchez
**Datum:** Januari 2026

---

## 📁 Project Structuur

```
PortfolioSensoDos/
├── backend/                              # Backend projecten
│   ├── project1-smart-room-monitor/      # Project 1: IoT room monitoring
│   ├── project2-behavior-analyzer/       # Project 2: Data analytics & ETL
│   └── project3-iot-gateway/             # Project 3: Device gateway & security
│
├── frontend/                             # React dashboard
│   └── src/
│       ├── components/                   # React components
│       ├── pages/                        # Page components
│       ├── stores/                       # Zustand state management
│       ├── hooks/                        # React Query custom hooks
│       ├── services/                     # API calls
│       ├── utils/                        # Helper functions
│       ├── DASHBOARD_MOCKUP.jsx          # Main dashboard code
│       └── DASHBOARD_STYLES.css          # Styling
│
└── docs/                                 # Documentatie
```

---

## 🚀 Projecten Overzicht


### 1. Smart Room Monitor (AWS Lambda)
**Tech Stack:** AWS Lambda, DynamoDB, API Gateway, CloudWatch, Python, Docker
**Status:** Getest met AWS (productie-achtige omgeving)
**Beschrijving:** Real-time monitoring van conferentiezalen met IoT sensoren

### 1b. Smart Room Monitor (FastAPI)
**Tech Stack:** FastAPI, DynamoDB Local, Docker, Python, React
**Status:** Getest met lokale Docker-stack (geen AWS nodig)
**Beschrijving:** Zelfde functionaliteit als project 1, maar volledig lokaal te draaien en te testen

### 2. Behavior Pattern Analyzer
**Tech Stack:** AWS Lambda, RDS PostgreSQL, Step Functions, Python, Docker
**Status:** Nog te ontwikkelen
**Beschrijving:** ETL pipeline voor detectie van gedragspatronen en anomalieën

### 3. IoT Device Gateway Simulator
**Tech Stack:** API Gateway, Cognito, DynamoDB, SQS, Python, Docker
**Status:** Nog te ontwikkelen
**Beschrijving:** Secure gateway voor IoT devices met auth en rate limiting

### 4. React Dashboard
**Tech Stack:** React, TanStack Query (React Query), Zustand, Chart.js, TailwindCSS
**Status:** Getest met zowel AWS-backend als lokale FastAPI-backend
**Beschrijving:** Dashboard voor visualisatie van alle backend projecten

---

## 📚 Documentatie

- **[Architectuur Overzicht](docs/architecture.md)** - Systeem architectuur en design principles
- **[Project 1: Smart Room Monitor](docs/project1-smart-room-monitor.md)** - API endpoints, database schema
- **[Project 2: Behavior Analyzer](docs/project2-behavior-analyzer.md)** - ETL pipeline, pattern detection
- **[Project 3: IoT Gateway](docs/project3-iot-gateway.md)** - Device management, security

---

## 🎯 Competenties Gedemonstreerd

✅ **Python OOP** - Domain models, services, repositories
✅ **RESTful APIs** - AWS API Gateway + Lambda
✅ **Databases** - PostgreSQL (RDS) + DynamoDB
✅ **Docker** - Containerization voor alle projecten
✅ **Git** - Clean commit geschiedenis
✅ **Distributed Systems** - Event-driven architectuur
✅ **IoT Context** - Sensor simulaties, low-power thinking
✅ **Testing** - Unit tests, integration tests (80%+ coverage)
✅ **Security** - JWT auth, rate limiting, input validation

---

## 🚀 CI/CD Pipeline & Deployment

- Automatische deployment via GitHub Actions (zie `.github/workflows/deploy.yml`).
- Testen worden automatisch uitgevoerd vóór deployment.
- CloudFormation-template (`backend/project1-smart-room-monitor/infrastructure/cloudformation.yaml`) beheert alle AWS resources: DynamoDB, Lambda, API Gateway.
- YAML-linting is uitgeschakeld voor CloudFormation-bestanden vanwege AWS-specifieke tags.

## 🗺️ Project Roadmap & Fases

1. Setup & documentatie
2. CI/CD pipeline
3. Infrastructure as Code (CloudFormation)
4. API development
5. Testing & coverage
6. Deployment
7. Monitoring & logging
8. Security & compliance
9. Demo & evaluatie

---

## 🧪 Testdata toevoegen aan DynamoDB

Om het dashboard te testen, voeg een testkamer toe aan DynamoDB:

1. Zorg dat je AWS credentials goed staan (via `aws configure`).
2. Voer het script uit:
   ```bash
   python backend/project1-smart-room-monitor/scripts/add_test_room.py
   ```
   - Dit script voegt een demo-kamer toe aan de tabel 'dev-RoomStatus'.
   - Zie het script voor commentaar en uitleg.
3. Herlaad de frontend: je ziet nu de testkamer in het dashboard.

---

##  Contact

**Email:** a.gonzalez.sanchez@gmail.com
**LinkedIn:** https://www.linkedin.com/in/GonzalezSanchez
**GitHub:** https://github.com/GonzalezSanchez

---

**Last Updated:** 7 januari 2026
**Status:** Project setup & planning fase
