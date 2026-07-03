# Project 4 — LLM / MCP Layer

## Description

An AI integration layer on top of the existing IoT platform. Exposes the FastAPI routes as MCP tools via `fastapi-mcp`, so an LLM (Claude or another agent) can query the platform directly in natural language.

**Example questions:**
- "Which rooms had anomalies this week?"
- "What is the current temperature in conference-a1?"
- "Show me the occupancy pattern for lab-d4 over the last 30 days."

## Why this is a strong portfolio project

Answers the interview question: *"Can you build AI-integrated systems?"*

It's also the capstone of the platform — every layer is now reachable:
- Project 1/1b → ingestion & API (backend)
- Project 2a → batch ETL + patterns (data engineering + backend)
- Project 2b → Airflow + PySpark (pure data engineering)
- Project 3 → device gateway (backend / security)
- Project 4 → AI layer (LLM + MCP)

## Tech Stack

- **`fastapi-mcp`** — automatically exposes FastAPI routes as MCP tools
- **Claude API** — natural language interface via Anthropic SDK
- **RAG** — retrieval over historical sensor data (pgvector on Aurora PostgreSQL, or locally via Chroma)
- **Docker** — local development

## Features

### 4a — MCP tools via fastapi-mcp
- Mount MCP server on existing FastAPI (project 1b)
- Every route automatically becomes a tool: `/rooms`, `/events`, `/insights`
- Claude can query the IoT platform directly

### 4b — Natural language interface
- Chatbot that answers questions about the platform
- Uses the MCP tools to fetch live data
- Example question → tool call → structured answer

### 4c — RAG over historical sensor data *(optional)*
- Embeddings of historical events and patterns
- Semantic search: "when were the meeting rooms busiest?"
- Vector store: pgvector (Aurora) or Chroma (local)

## Architecture

```
User (natural language, via frontend "LLM + MCP" tab)
        │
        ▼
nginx  /ai/*  ──►  project4-ai-assistant (separate container)
                        │
                        ├── Claude API (Anthropic SDK, async + streaming)
                        │
                        └── MCP tools ──► HTTP ──► project 1b FastAPI
                                                      ├── GET /rooms
                                                      ├── GET /events
                                                      ├── GET /insights/...   (project 2a)
                                                      └── GET /lakehouse/...  (project 2c)
```

## Design decisions

**Separate service, not mounted on 1b.** The AI layer runs as its own container
(`project4-ai-assistant`) alongside the existing production API, with its own nginx route (`/ai`).
The MCP tools call the 1b API via HTTP instead of direct function calls.
Reason: blast radius — a bug or hanging LLM call in the AI layer can't take down the live demo at
iot.gonzalezsanchez.dev, and the `anthropic` dependency stays out of the stable
1b service. Every iteration on project 4 deploys without restarting the production API.

**Async from day one.** Three reasons, different from project 3 (which is about concurrent
devices):

1. *Parallel tool calls* — a single question may need several MCP tools at once
   (`asyncio.gather` over `/insights` + `/rooms`)
2. *Streaming* — Claude's answer arrives token by token (5-30s); pipe it straight to the
   frontend via SSE instead of waiting for the full response
3. *Slow I/O* — an LLM call takes seconds; a sync route would keep a thread
   occupied that whole time

**Model choice: Claude Haiku 4.5** (`claude-haiku-4-5`, $1/$5 per million tokens).
Cheapest model, more than sufficient for tool-calling over a small API. Upgrading to
Sonnet is a one-line config change if tool calls start missing too often. Estimated cost at
portfolio traffic: cents up to ~€1/month. Requires its own Anthropic API key
(separate from the Claude Code subscription) — stored in `.env.prod`, never committed.

**Cost and abuse protection** (public endpoint, every call costs money):

| Layer | Measure | Effect |
|---|---|---|
| 1. Rate limiting | `slowapi` per IP: 5/min, 20/day | Bot blocked after 5 requests (429) |
| 2. Token cap | `max_tokens=1024`, history max ~6 messages | An accepted request costs at most ~half a cent |
| 3. Spend limit | Anthropic Console monthly budget (~$5) | Hard floor — API refuses above it |
| 4. Cloudflare | Tunnel filters bots/DDoS before the server | Free first line of defense |

Worst case: an aggressive bot costs at most the spend limit. Same cost discipline as
the Azure budget alert on project 2c.

## Security

The cost table above protects the wallet; this section protects the platform. An LLM with
tools on a public endpoint has its own attack surface, and the defenses are structural —
prompt instructions alone cannot prevent prompt injection.

**Least-privilege tool surface.** Only read-only GET routes are exposed as MCP tools
(`fastapi-mcp` include/exclude filters per route or tag). `POST /events` and any other
writing route are explicitly excluded. Prompt injection ("send 1000 events to room-1")
then has nothing to abuse: the brain can only read data that is already public via the
dashboard. This is the single most important control.

**MCP endpoint stays internal.** The MCP server mounted on the 1b API is reachable only
inside the Docker network (for the AI service). It is never routed through nginx to the
outside — otherwise anyone could bypass the rate limiting and spend controls by connecting
their own agent directly to the MCP server.

**Real client IP behind the Cloudflare tunnel.** All traffic arrives via the tunnel, so
to `slowapi` every request appears to come from the same IP. Rate limiting must key on the
`CF-Connecting-IP` header instead of the socket address — otherwise the whole world shares
one 5/min budget and a single bot makes the chatbot unusable for everyone.

**LLM output is untrusted frontend input.** The chat tab renders answers as plain
text/markdown — never `dangerouslySetInnerHTML`. A prompt-injected answer containing
`<script>` must render as text, not execute.

**API key hygiene.** The Anthropic key lives in `.env.prod` (gitignored), is never
committed, and never appears in logs or error responses — Anthropic SDK exceptions are
caught and mapped to generic error messages before anything reaches the client. The
Console spend limit is the hard backstop if the key ever leaks.

**Operational hardening.**
- Timeout on every Claude call, so a hanging request cannot pin an SSE connection open
- Maximum length on the user message (input side of the existing `max_tokens` output cap)
- Tool calls logged per client IP for abuse detection
- Container runs as a non-root user

**Out of scope by design:** user authentication (public portfolio demo — rate limits are
the access control) and device security (project 3 scope).

## Relationship to existing projects

- Calls **project 1b** (FastAPI) via HTTP — no changes needed to the existing routes
- Fetches analytics data via the **project 2a** API (`/insights`) and **project 2c** (`/lakehouse/*`)
- Frontend: the "LLM + MCP" tab already exists as a ComingSoon placeholder in `App.jsx`
- Infrastructure: extra container in `docker-compose.prod.yml` + nginx route, no extra AWS resources

## When

Implemented before project 3 — smaller in scope and aligned with the AI direction
in the job market. Order: 4a (MCP tools) → 4b (chat + streaming + frontend tab) → 4c/4d later.

---

## Databricks MCP integration (extension 4d)

### What is it?

Alongside `fastapi-mcp` on the IoT API there's also a **native Databricks MCP server** — part of the **Databricks AI Dev Kit**. It gives an LLM direct access to the Databricks workspace: Unity Catalog tables, SQL Warehouse, job runs, notebooks.

While 4a/4b cover the IoT API, 4d would cover the lakehouse data (project 2c):

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

**Example questions via Databricks MCP:**
- "How many anomalies were detected in the last pipeline run?"
- "Show me the Gold layer schema for fact_anomalies."
- "Trigger a new pipeline run."

### Databricks AI Dev Kit

Several Databricks MVPs (including Jaco van Gelder) recommend the **AI Dev Kit** as a starting point — it includes an MCP server plus prebuilt skills for Databricks. Advantage: no need to build your own MCP implementation, just configure it.

Installation:
```bash
uvx databricks-ai-dev-kit
```

Or via Claude Code MCP config:
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

### Caveats (from LinkedIn discussion)

- **Day 2 operations**: MCP is strong for scaffolding and prototyping — but schema drift, unit tests, and state management require human governance (Siva Kandula, Senior ML Engineer @ ServiceNow)
- **Synthetic data**: high ML accuracy comes from clean synthetic data, not from the model — in production, data is always messier
- **Databricks Genie**: an alternative for SQL-based questions directly in the workspace, without an external LLM

### When

After 4a/4b. Requires an active Databricks workspace (project 2c).

---

## RAG Implementation Notes

*Based on reference guide: "Build a RAG AI Agent From Scratch" (Akhila G, 2026)*

### Our source vs PDFs

Her guide uses PDF files as the knowledge source. Our source is historical sensor data in Aurora PostgreSQL (`raw_sensor_data`, `patterns`, `anomalies`). The principle is identical — the data needs to be chunked and embedded for vector search queries.

### Chunking strategy

Use `tiktoken` for token-based chunking with overlap:

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

**Rules of thumb:**
- 450 tokens per chunk, 80 overlap — a good starting point
- Too large → unfocused answers
- Too small → loss of context

### Vector store: pgvector (Aurora)

No separate FAISS service needed — pgvector is a PostgreSQL extension that already runs on Aurora:

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
User question
    │
    ▼
Embed query (Claude embeddings or open model)
    │
    ▼
pgvector cosine search → top-k relevant chunks
    │
    ▼
Build context (merge chunks)
    │
    ▼
Claude API — generate answer based on context
    │
    ▼
Grounded answer (no hallucinations)
```

### Difference from her approach

| Aspect | Reference (Akhila G) | Project 4 |
|---|---|---|
| Source | PDF files | Aurora PostgreSQL |
| Vector store | FAISS (local) | pgvector (Aurora — already present) |
| Embeddings | OpenAI text-embedding-3-small | Claude or open model |
| Generation | GPT-4o | Claude API (Anthropic) |
| Extra layer | — | MCP via fastapi-mcp |
