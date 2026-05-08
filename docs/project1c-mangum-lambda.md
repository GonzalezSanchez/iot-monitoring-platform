# Project 1c — FastAPI via Mangum in Lambda

## Beschrijving

Dezelfde FastAPI applicatie als project 1b, maar deployed als AWS Lambda functie
via Mangum. Demonstreert dat dezelfde codebase in drie verschillende deployment
modellen kan draaien.

**Progressie in project 1:**

| Project | Model | Beschrijving |
|---------|-------|--------------|
| 1a | Serverless (Lambda) | Pure Lambda handlers, event-driven, geen framework |
| 1b | Container (FastAPI) | FastAPI in Docker, altijd draaiend, REST API |
| 1c | FastAPI in Lambda | Mangum adapter — FastAPI als Lambda handler |

## Wat is Mangum?

Mangum is een ASGI adapter voor AWS Lambda. Het vertaalt het AWS Lambda event
formaat naar ASGI-compatible requests zodat FastAPI (of elke andere ASGI app)
direct als Lambda handler kan draaien.

```
API Gateway event  →  Mangum  →  FastAPI  →  Mangum  →  API Gateway response
```

Twee regels code:
```python
from mangum import Mangum
handler = Mangum(app)  # app is de bestaande FastAPI instantie
```

## Wat verandert t.o.v. project 1b?

- `handler = Mangum(app)` toevoegen aan `main.py`
- Dockerfile vervangen door Lambda deployment package
- Docker Compose niet meer nodig — Lambda beheert alles
- Terraform uitbreiden met Lambda functie + API Gateway

## Voordelen vs 1b

- Geen server/container om te beheren
- Automatisch schalen
- Pay per request (goedkoper bij laag verkeer)

## Nadelen vs 1b

- Cold starts bij eerste request
- FastAPI lifespan events werken anders in Lambda
- Minder controle over de omgeving

## Status

Gepland — na project 4.
