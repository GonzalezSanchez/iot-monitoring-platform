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
