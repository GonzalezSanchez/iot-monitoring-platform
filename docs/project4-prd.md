# PRD — Project 4: LLM / MCP Layer

> Build contract for the implementation. The public spec is `docs/project4-llm-mcp.md`
> (architecture, rationale, security principles) — this document makes that spec
> executable: exact tool surface, test contract, and acceptance criteria. On conflict,
> this document wins on names/details; the spec wins on architecture decisions.
>
> Method: PRD first, minimal freedom during the build, tests written alongside the code.

## 1. Goal

An AI layer on top of the existing platform, in two steps:

- **4a** — the 1b FastAPI exposes its read-only routes as MCP tools (`fastapi-mcp`)
- **4b** — a separate AI service (`project4-ai-assistant`) where Claude Haiku answers
  natural-language questions through those MCP tools, streamed to the frontend

This PRD specifies **4a in full** (§3–§7) and **4b at design level** (§8) — 4b gets
refined before its build starts.

## 2. Non-goals

- RAG / pgvector (4c) and Databricks MCP (4d) — later extensions
- User authentication — rate limits are the access control (public demo)
- Changes to existing 1b business logic — 4a only adds an MCP layer

---

## 3. 4a — Scope

One service changes: **project 1b** (`backend/project1b-smart-room-monitor-fastapi`).

1. Add the `fastapi-mcp` dependency to `requirements.txt` — **pinned** to the version
   current at implementation time (check PyPI; the API differs between versions, so
   pin exactly).
2. Explicit `operation_id` on the GET routes to be exposed — fastapi-mcp uses the
   operation_id as the tool name; without an explicit id Claude sees ugly names like
   `get_rooms_rooms_get`. This only changes `openapi.json`, not route behavior.
3. Mount the MCP server on the existing app at path `/mcp`, with an **allowlist**
   (`include_operations`) — never a denylist.

## 4. 4a — Tool surface (allowlist)

Exactly these **7 tools**, nothing else:

| operation_id | Route | Purpose |
|---|---|---|
| `get_rooms` | GET /rooms | room list + current state |
| `get_room` | GET /rooms/{room_id} | single room detail |
| `get_room_events` | GET /rooms/{room_id}/events | events per room |
| `get_events` | GET /events | events (optional room_id filter) |
| `get_lakehouse_summary` | GET /lakehouse/summary | Gold-layer totals (2c) |
| `get_lakehouse_anomalies` | GET /lakehouse/anomalies | recent anomalies (2c) |
| `get_lakehouse_rooms` | GET /lakehouse/rooms | room dimensions (2c) |

**Explicitly excluded:**

- `POST /events` (`create_event`) — the only writing route; prompt injection must be
  structurally unable to write anything. This is the single most important security
  control of 4a.
- `GET /health` — useless as an LLM tool, pollutes the tool list.
- `GET /docs`, `/openapi.json` — not tools.

## 5. 4a — Security requirements (from docs/project4-llm-mcp.md §Security)

- **Allowlist, not denylist**: a new route added to 1b must never silently become a
  tool. `include_operations` with the 7 names from §4.
- **/mcp stays internal**: the nginx location regex in `frontend/nginx.conf`
  (`rooms|events|health|docs|openapi.json|lakehouse`) **never** gets `mcp` added.
  The backend container uses `expose` (not `ports`) in `docker-compose.prod.yml`,
  so /mcp is only reachable inside the Docker network. Both facts are guarded by a
  test/smoke check (§6).
- No new env vars, no secrets — 4a introduces no key material.

## 6. 4a — Test contract

Existing: 12 tests in `tests/test_endpoints.py` — these stay green unchanged.

New (`tests/test_mcp.py`):

1. **Tool set is exactly the allowlist** — the core regression test: the set of
   exposed tools == the 7 names from §4, and `create_event` is NOT among them. If
   this test fails it is a security regression, not a style issue.
2. **/mcp exists** — the mount answers the MCP handshake/endpoint (exact shape
   depends on the fastapi-mcp transport; SSE or streamable HTTP).
3. **Existing routes untouched** — `openapi.json` still contains the same
   paths+methods as before the change (operation_ids may differ).

Production smoke test (after deploy, manual or in the deploy checklist):

- `curl https://iot.gonzalezsanchez.dev/mcp` → **no** MCP response (404/frontend fallback)
- From the Docker network on the server: `docker compose exec frontend curl
  http://backend:8000/mcp` → MCP response present

## 7. 4a — Acceptance criteria

- [ ] An MCP client inside the Docker network can connect to `http://backend:8000/mcp`
      and sees exactly 7 tools with the names from §4
- [ ] All existing 1b tests green, plus the 3 new MCP tests
- [ ] `/mcp` not reachable via iot.gonzalezsanchez.dev
- [ ] Frontend works unchanged (same routes, same responses)
- [ ] CI green; merged via PR

---

## 8. 4b — Design frame (to be refined before the build)

Agent architecture (Brain / Tools / Memory / Loop), applied:

- **Brain**: system prompt in `brain.md`, loaded at runtime — never a hardcoded
  string. Model `claude-haiku-4-5` via the official `anthropic` SDK.
- **Tools**: the 7 MCP tools from 4a, via the official `mcp` Python client over
  streamable HTTP to `http://backend:8000/mcp` — no hand-written httpx wrappers
  (rich tool surface → use MCP).
- **Loop**: bounded (`for step in range(N)`); the agentic part is only answering the
  question — everything around it (SSE framing, rate limiting, history cap) is
  deterministic workflow code.
- **Memory**: none — each chat session is stateless apart from the history in the
  request body (max 6 messages).

Security/operational (from the public spec): slowapi keyed on `CF-Connecting-IP`,
timeout on every Claude call, max input length, tool calls logged per IP, non-root
container, API key only in `.env.prod`. Full elaboration (SSE event schema, error
matrix, test contract) will be added as a 4b section in this PRD once 4a is done.

## 9. Build order

4a is built on branch `feature/project4a-mcp`, one PR. Order: dependency pin →
operation_ids → mount with allowlist → tests → prod smoke check after deploy.
