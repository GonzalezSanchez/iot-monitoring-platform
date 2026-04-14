# Project 4 — LLM / MCP Layer

## Beschrijving

Een AI-integratie laag bovenop het bestaande IoT platform. Exposeert de FastAPI routes als MCP tools via `fastapi-mcp`, zodat een LLM (Claude of andere agent) het platform direct kan bevragen in natuurlijke taal.

**Voorbeeldvragen:**
- "Which rooms had anomalies this week?"
- "What is the current temperature in conference-a1?"
- "Show me the occupancy pattern for lab-d4 over the last 30 days."

## Waarom dit een sterk portfolio project is

Beantwoordt de interviewvraag: *"Can you build AI-integrated systems?"*

Het is ook het sluitstuk van het platform — elke laag is nu bereikbaar:
- Project 1/1b → ingestion & API (backend)
- Project 2a → batch ETL + patterns (data engineering + backend)
- Project 2b → Airflow + PySpark (pure data engineering)
- Project 3 → device gateway (backend / security)
- Project 4 → AI layer (LLM + MCP)

## Tech Stack

- **`fastapi-mcp`** — exposeert FastAPI routes automatisch als MCP tools
- **Claude API** — natural language interface via Anthropic SDK
- **RAG** — retrieval over historische sensordata (pgvector op Aurora PostgreSQL, of lokaal via Chroma)
- **Docker** — lokale development

## Features

### 4a — MCP tools via fastapi-mcp
- Mount MCP server op bestaande FastAPI (project 1b)
- Elke route wordt automatisch een tool: `/rooms`, `/events`, `/insights`
- Claude kan direct het IoT platform bevragen

### 4b — Natural language interface
- Chatbot die vragen over het platform beantwoordt
- Gebruikt de MCP tools om live data op te halen
- Voorbeeldvraag → tool call → gestructureerd antwoord

### 4c — RAG op historische sensordata *(optioneel)*
- Embeddings van historische events en patronen
- Semantisch zoeken: "wanneer was het drukst in de vergaderzalen?"
- Vector store: pgvector (Aurora) of Chroma (lokaal)

## Architectuur

```
Gebruiker (natuurlijke taal)
        │
        ▼
Claude / LLM Agent
        │  (MCP protocol)
        ▼
fastapi-mcp server  ←── gemount op project 1b FastAPI
        │
        ├── GET /rooms          → lijst kamers + status
        ├── GET /events         → sensor events opvragen
        ├── GET /insights/...   → patterns + anomalies (project 2a)
        └── POST /events        → sensor event injecteren
```

## Relatie met bestaande projecten

- Bouwt bovenop **project 1b** (FastAPI) — geen wijzigingen aan de bestaande routes nodig
- Haalt analytics data op via **project 2a** API (`/insights`)
- Infrastructuur: lokaal via Docker, geen extra AWS resources nodig

## Wanneer

Na project 3. Dit is het finale sluitstuk van het platform.
