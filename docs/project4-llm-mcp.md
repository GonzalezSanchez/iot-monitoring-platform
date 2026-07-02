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
Gebruiker (natuurlijke taal, via frontend "LLM + MCP" tab)
        │
        ▼
nginx  /ai/*  ──►  project4-ai-assistant (aparte container)
                        │
                        ├── Claude API (Anthropic SDK, async + streaming)
                        │
                        └── MCP tools ──► HTTP ──► project 1b FastAPI
                                                      ├── GET /rooms
                                                      ├── GET /events
                                                      ├── GET /insights/...   (project 2a)
                                                      └── GET /lakehouse/...  (project 2c)
```

## Ontwerpbeslissingen

**Aparte service, niet gemount op 1b.** De AI-laag draait als eigen container
(`project4-ai-assistant`) naast de bestaande productie-API, met een eigen nginx-route (`/ai`).
De MCP tools roepen de 1b API aan via HTTP in plaats van directe function calls.
Reden: blast radius — een bug of hangende LLM-call in de AI-laag kan de live demo op
iot.gonzalezsanchez.dev niet meetrekken, en de `anthropic` dependency blijft uit de stabiele
1b service. Elke iteratie aan project 4 deployt zonder de productie-API te herstarten.

**Async vanaf dag één.** Drie redenen, anders dan bij project 3 (waar het om concurrente
devices gaat):

1. *Parallelle tool calls* — één vraag kan meerdere MCP tools tegelijk nodig hebben
   (`asyncio.gather` over `/insights` + `/rooms`)
2. *Streaming* — Claude's antwoord komt token per token binnen (5-30s); via SSE direct
   doorsturen naar de frontend in plaats van wachten op het volledige antwoord
3. *Trage I/O* — een LLM-call duurt seconden; een sync route zou al die tijd een thread
   bezet houden

**Modelkeuze: Claude Haiku 4.5** (`claude-haiku-4-5`, $1/$5 per miljoen tokens).
Goedkoopste model, ruim voldoende voor tool-calling over een kleine API. Upgrade naar
Sonnet is één regel config als tool-aanroepen te vaak missen. Geschatte kosten bij
portfolio-verkeer: centen tot ~€1/maand. Vereist een eigen Anthropic API key
(los van het Claude Code abonnement) — in `.env.prod`, nooit gecommit.

**Kosten- en misbruikbescherming** (publiek endpoint, elke call kost geld):

| Laag | Maatregel | Effect |
|---|---|---|
| 1. Rate limiting | `slowapi` per IP: 5/min, 20/dag | Bot geblokkeerd na 5 requests (429) |
| 2. Token cap | `max_tokens=1024`, history max ~6 berichten | Doorgelaten request kost max ~halve cent |
| 3. Spend limit | Anthropic Console maandbudget (~$5) | Harde ondergrens — API weigert daarboven |
| 4. Cloudflare | Tunnel filtert bots/DDoS al vóór de server | Gratis eerste verdedigingslinie |

Worst case: een agressieve bot kost maximaal het spend limit. Zelfde kostendiscipline als
de Azure budget alert bij project 2c.

## Relatie met bestaande projecten

- Roept **project 1b** (FastAPI) aan via HTTP — geen wijzigingen aan de bestaande routes nodig
- Haalt analytics data op via **project 2a** API (`/insights`) en **project 2c** (`/lakehouse/*`)
- Frontend: de "LLM + MCP" tab bestaat al als ComingSoon-placeholder in `App.jsx`
- Infrastructuur: extra container in `docker-compose.prod.yml` + nginx-route, geen extra AWS resources

## Wanneer

Wordt vóór project 3 geïmplementeerd — kleiner in scope en sluit aan bij de AI-richting
op de arbeidsmarkt. Volgorde: 4a (MCP tools) → 4b (chat + streaming + frontend tab) → 4c/4d later.

---

## Databricks MCP integratie (uitbreiding 4d)

### Wat is het?

Naast `fastapi-mcp` op de IoT API bestaat er ook een **native Databricks MCP server** — onderdeel van de **Databricks AI Dev Kit**. Deze geeft een LLM directe toegang tot de Databricks workspace: Unity Catalog tabellen, SQL Warehouse, job runs, notebooks.

Terwijl 4a/4b over de IoT API gaan, zou 4d over de lakehouse data gaan (project 2c):

```
Claude Agent
    │
    ├── fastapi-mcp (4a)          → IoT API: /rooms, /events, /insights
    │
    └── Databricks MCP (4d)       → Lakehouse: Gold tables, job runs, Unity Catalog
            │
            ├── SQL Warehouse     → SELECT * FROM gold.fact_anomalies
            ├── Jobs API          → trigger/monitor pipeline runs
            └── Unity Catalog     → schema discovery, lineage
```

**Voorbeeldvragen via Databricks MCP:**
- "How many anomalies were detected in the last pipeline run?"
- "Show me the Gold layer schema for fact_anomalies."
- "Trigger a new pipeline run."

### Databricks AI Dev Kit

Meerdere Databricks MVPs (o.a. Jaco van Gelder) raden de **AI Dev Kit** aan als startpunt — bevat MCP server + prebuilt skills voor Databricks. Voordeel: geen eigen MCP implementatie nodig, gewoon configureren.

Installatie:
```bash
uvx databricks-ai-dev-kit
```

Of via Claude Code MCP config:
```json
{
  "mcpServers": {
    "databricks": {
      "command": "uvx",
      "args": ["databricks-mcp-server"],
      "env": {
        "DATABRICKS_HOST": "https://adb-7405609278521333.13.azuredatabricks.net",
        "DATABRICKS_TOKEN": "<PAT>"
      }
    }
  }
}
```

### Kanttekeningen (van LinkedIn discussie)

- **Day 2 operations**: MCP is sterk voor scaffolding en prototyping — maar schema drift, unit tests en state management vereisen menselijke governance (Siva Kandula, Senior ML Engineer @ ServiceNow)
- **Synthetic data**: hoge ML accuracy komt door schone synthetische data, niet door het model — in productie is data altijd messier
- **Databricks Genie**: alternatief voor SQL-gebaseerde vragen direct in de workspace, zonder externe LLM

### Wanneer

Na 4a/4b. Vereist actieve Databricks workspace (project 2c).

---

## RAG Implementatienotes

*Gebaseerd op referentiegids: "Build a RAG AI Agent From Scratch" (Akhila G, 2026)*

### Onze bron vs PDFs

Haar gids gebruikt PDF-bestanden als kennisbron. Onze bron is historische sensordata in Aurora PostgreSQL (`raw_sensor_data`, `patterns`, `anomalies`). Het principe is identiek — de data moet gechuunkt en geëmbed worden voor vectorzoekopdrachten.

### Chunking strategie

Gebruik `tiktoken` voor token-gebaseerde chunking met overlap:

```python
import tiktoken

def chunk_sensor_data(text: str, chunk_tokens: int = 450,
                      overlap_tokens: int = 80) -> list[str]:
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = start + chunk_tokens
        chunk = enc.decode(tokens[start:end])
        chunks.append(chunk)
        start = end - overlap_tokens
    return chunks
```

**Vuistregels:**
- 450 tokens per chunk, 80 overlap — goed startpunt
- Te groot → ongerichte antwoorden
- Te klein → verlies van context

### Vector store: pgvector (Aurora)

Geen aparte FAISS service nodig — pgvector is een PostgreSQL extensie die al op Aurora draait:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE sensor_embeddings (
    id UUID PRIMARY KEY,
    chunk_text TEXT NOT NULL,
    embedding VECTOR(1536),
    source_table VARCHAR(50),  -- 'raw_sensor_data', 'patterns', 'anomalies'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON sensor_embeddings
    USING ivfflat (embedding vector_cosine_ops);
```

### RAG flow

```
Gebruikersvraag
    │
    ▼
Embed query (Claude embeddings of open model)
    │
    ▼
pgvector cosine search → top-k relevante chunks
    │
    ▼
Context opbouwen (chunks samenvoegen)
    │
    ▼
Claude API — antwoord genereren op basis van context
    │
    ▼
Gegrond antwoord (geen hallucinaties)
```

### Verschil met haar aanpak

| Aspect | Referentie (Akhila G) | Project 4 |
|---|---|---|
| Bron | PDF bestanden | Aurora PostgreSQL |
| Vector store | FAISS (lokaal) | pgvector (Aurora — al aanwezig) |
| Embeddings | OpenAI text-embedding-3-small | Claude of open model |
| Generatie | GPT-4o | Claude API (Anthropic) |
| Extra laag | — | MCP via fastapi-mcp |
