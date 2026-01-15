# Project 1b — Smart Room Monitor (FastAPI)

## Overzicht
Dit document beschrijft de FastAPI-versie van de Smart Room Monitor backend (project1b). Het bevat uitleg over de architectuur, gebruikte technologieën, endpoints, en migratie vanuit de oorspronkelijke Lambda-implementatie.

## Inhoud
- Doel en scope
- Architectuuroverzicht
- Verschillen t.o.v. Lambda-versie
- API-endpoints
- Hergebruikte code
- Installatie en starten
- Toekomstige uitbreidingen

## 1. Doel en scope
Deze backend biedt een REST API voor het monitoren van ruimtes en sensorgegevens, als alternatief voor de serverless Lambda-oplossing.

## 2. Architectuuroverzicht
- **Framework:** FastAPI
- **Database:** DynamoDB (via boto3)
- **Structuur:** models/, repositories/, services/, utils/
- **API:** REST endpoints voor rooms en events

## 3. Verschillen t.o.v. Lambda-versie
- Geen AWS Lambda, maar een eigen FastAPI-server
- Eenvoudiger lokaal te testen en uit te breiden
- Zelf verantwoordelijk voor hosting en scaling

## 4. API-endpoints (voorbeeld)
- `GET /rooms` — lijst van alle ruimtes
- `GET /rooms/{room_id}` — details van één ruimte
- `POST /events` — nieuw event toevoegen

## 5. Hergebruikte code
- Models, repositories en services grotendeels overgenomen uit project1
- Aanpassingen voor FastAPI routing en dependency injection

## 6. Installatie en starten
```bash
cd backend/project1b-smart-room-monitor-fastapi
pip install -r requirements.txt
uvicorn main:app --reload
```

## 7. Toekomstige uitbreidingen
- Authenticatie/authorisatie
- Meer endpoints (bijv. voor sensoren)
- Integratie met frontend

---
Zie ook het stappenplan in `docs/STAPPEN_PROJECT1B.md` voor een gedetailleerde ontwikkelroute.
