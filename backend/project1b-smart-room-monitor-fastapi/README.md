# ![CI](https://github.com/GonzalezSanchez/iot-monitoring-platform/actions/workflows/ci.yml/badge.svg)
# Smart Room Monitor (FastAPI) — Project 1b

Real-time IoT monitoring system for conference rooms using FastAPI (Python) as an alternative to the AWS Lambda variant (project 1).

## 🎯 Overzicht

Dit project demonstreert:
- ✅ Python OOP met clean architecture
- ✅ FastAPI + DynamoDB
- ✅ Docker containerization
- ✅ Unit testing met pytest
- ✅ IoT sensor simulatie

## 🏗️ Architectuur

```
IoT Sensors → FastAPI Endpoints → Business Logic/Repositories → DynamoDB
```


## 🚀 Snel starten

- `main.py` — FastAPI entrypoint en endpoints
- `requirements.txt` — dependencies
- `models/` — datamodellen (herbruikbaar uit project1)
- `repositories/` — data access/repository-laag (herbruikbaar uit project1)
- `services/` — business logic (herbruikbaar uit project1)
- `utils/` — hulpfuncties

## Snel starten


### Prerequisites
- Python 3.11+
- Docker (optioneel)

### Local Development
1. Clone de repository en ga naar de projectmap:
	```bash
	git clone <repo-url>
	cd backend/project1b-smart-room-monitor-fastapi
	```
2. Maak een virtual environment aan en installeer dependencies:
	```bash
	python3 -m venv .venv
	source .venv/bin/activate
	pip install -r requirements-dev.txt
	```
3. Start de FastAPI server:
	```bash
	uvicorn main:app --reload
	```

> **Tip:** Gebruik requirements-dev.txt voor development (inclusief linting, tests, etc). requirements.txt is voor productie.


## 📡 API Endpoints

- `GET /rooms` — lijst van kamers
- `GET /rooms/{room_id}` — details van een kamer


## 🏗️ Projectstructuur

- `main.py` — FastAPI entrypoint en endpoints
- `requirements.txt` — dependencies
- `models/` — datamodellen (herbruikbaar uit project1)
- `repositories/` — data access/repository-laag (herbruikbaar uit project1)
- `services/` — business logic (herbruikbaar uit project1)
- `utils/` — hulpfuncties

## ♻️ Hergebruik uit project 1
Je kunt code uit project1 (Lambda) direct hergebruiken in de `models/`, `repositories/` en `services/` folders. Alleen de API-laag (handlers) moet je herschrijven naar FastAPI-routes.


## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html
```

## 🛳️ Deployment

Deployment naar productie kan via Docker of een eigen server. Zie project1 voor best practices.

## TODO
- [ ] Models, repositories en services kopiëren/aanpassen uit project1
- [ ] DynamoDB-verbinding toevoegen (of mocken voor lokaal testen)
- [ ] Endpoints koppelen aan echte logica
- [ ] Testen met curl of frontend
- [ ] Documentatie bijwerken


> **Notitie:**
> Deze map is voorbereid voor verdere ontwikkeling. Zie project1 voor bestaande business logica en datamodellen.
