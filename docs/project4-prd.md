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

This PRD specifies **4a in full** (§3–§7) and **4b in full** (§8–§13).

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

## 8. 4b — Design frame

Agent architecture (Brain / Tools / Memory / Loop), applied:

- **Brain**: system prompt in `brain.md`, loaded at runtime — never a hardcoded
  string. Model `claude-haiku-4-5` via the official `anthropic` SDK (`AsyncAnthropic`).
- **Tools**: the 7 MCP tools from 4a, discovered via the official `mcp` Python client
  over streamable HTTP to `http://backend:8000/mcp` — no hand-written httpx wrappers
  (rich tool surface → use MCP). See §9 for why this is a hand-written manual loop
  rather than the SDK's `tool_runner` helper.
- **Loop**: bounded (`for step in range(MAX_STEPS)`, `MAX_STEPS = 8`); the agentic
  part is only answering the question — everything around it (SSE framing, rate
  limiting, history cap) is deterministic workflow code.
- **Memory**: none — each chat session is stateless apart from the history in the
  request body (max `MAX_HISTORY_MESSAGES = 6` messages).

Security/operational (from `docs/project4-llm-mcp.md` §Security): slowapi keyed on
`CF-Connecting-IP`, timeout on every Claude call, max input length, tool calls logged
per IP, non-root container, API key only in `.env.prod`.

## 9. 4b — Loop & streaming design

**Why a manual loop, not `tool_runner`.** The Anthropic Python SDK's tool runner
(`client.beta.messages.tool_runner`) drives the agentic loop automatically but only
returns complete messages — it does not stream individual tokens. Since the frontend
needs live token-by-token output over SSE, `/ai/chat` uses a manual loop built on
`client.messages.stream(...)`, forwarding text deltas as they arrive and only
inspecting the full response once each turn's stream completes.

**Why the official `mcp` client instead of the SDK's MCP-to-tool_runner helpers.**
`anthropic.lib.tools.mcp.async_mcp_tool` exists to plug MCP tools into `tool_runner`
— it is not meant for a manual loop. Instead: connect once with
`mcp.client.streamable_http.streamablehttp_client` + `mcp.ClientSession`, call
`session.list_tools()` to get the MCP `Tool` objects (name, description,
`inputSchema`), and translate each into a plain Anthropic tool dict
(`{"name":, "description":, "input_schema":}`) for the `tools=` parameter. On a
`tool_use` block, call `session.call_tool(name, input)` directly and feed the result
back as a `tool_result` message. This is the same 4a-validated connection pattern
(§7's acceptance check already proved a real MCP client sees exactly 7 tools here).

**MCP session lifecycle.** One long-lived `ClientSession` per service instance,
opened in the FastAPI `lifespan` at startup; the tool list is discovered once and
cached. If 1b is unreachable at startup, the service still starts, but `/ai/chat`
fails fast with a 503 instead of hanging on a dead connection.

**Request flow (`POST /ai/chat`):**

1. Validate: `messages` non-empty, no message over `MAX_INPUT_CHARS`; truncate
   history to the last `MAX_HISTORY_MESSAGES`.
2. Rate-limit check (`slowapi`, keyed on `CF-Connecting-IP`) — **before** the SSE
   stream opens, so a limit hit is a plain HTTP 429, never a mid-stream surprise.
3. Open a `StreamingResponse` (`text/event-stream`) and run the bounded loop:
   a. `async with client.messages.stream(model="claude-haiku-4-5", system=BRAIN_PROMPT, max_tokens=1024, tools=TOOLS_SCHEMA, messages=messages) as stream:` —
      forward each `text_delta` live as a `token` SSE event.
   b. After the stream ends, `response = await stream.get_final_message()`; append
      it to `messages`.
   c. If `response.stop_reason != "tool_use"`: emit `done`, stop.
   d. Else: for each `tool_use` block, emit a `tool_use` event, call
      `session.call_tool(name, input)`, append the result as a `tool_result`
      message, and continue the loop.
4. If the loop exhausts `MAX_STEPS` without an `end_turn`: emit an `error` event
   (`step_limit_reached`) — a workflow safeguard, not an expected outcome given the
   small, read-only tool surface.

## 10. 4b — SSE event schema

| event `type` | payload fields | when |
|---|---|---|
| `token` | `content: str` | live per-token text as Claude answers |
| `tool_use` | `name: str` | Claude is calling an MCP tool (frontend shows a "thinking: {name}" badge) |
| `done` | — | turn complete, stream closes |
| `error` | `code: str`, `message: str` | see error matrix below; stream closes after this event |

## 11. 4b — Error matrix

| Condition | Response | User-facing detail |
|---|---|---|
| Empty `messages` | HTTP 422 (before stream opens) | FastAPI validation error |
| Message over `MAX_INPUT_CHARS` | HTTP 422 (before stream opens) | operational hardening, §Security |
| Rate limit exceeded | HTTP 429 (before stream opens) | "Too many requests, try again in Xs" |
| Anthropic API error mid-stream (`RateLimitError`, `APIStatusError`, timeout) | SSE `error`, `code: "llm_unavailable"` | generic message only — never the raw exception (API key hygiene, §Security) |
| MCP tool call fails (1b down, bad input) | `tool_result` with `is_error: true` fed back to Claude | Claude explains it couldn't fetch the data — not a hard error unless Claude itself gives up |
| Step limit reached | SSE `error`, `code: "step_limit_reached"` | "Reached the maximum number of steps for this answer" |
| 1b/MCP unreachable at service startup | Service starts; `/ai/chat` returns 503 | "AI assistant temporarily unavailable" |

## 12. 4b — Test contract

`tests/test_chat_service.py` (Anthropic client and MCP session both mocked — no real
API or network calls):

1. **Text-only turn**: mocked stream yields `text_delta`s → tokens forwarded in
   order → `done`.
2. **Tool-use turn**: mocked `stop_reason="tool_use"` → `tool_use` event carries the
   correct name → mocked `session.call_tool` is called with the exact tool name and
   arguments Claude produced → loop continues with the tool result appended →
   second turn ends the loop with `done`.
3. **History cap**: a request with more than `MAX_HISTORY_MESSAGES` messages has the
   oldest ones dropped before the first API call.
4. **Step limit**: a stream that always returns `stop_reason="tool_use"` stops at
   `MAX_STEPS` and yields `step_limit_reached` — never an infinite loop.

`tests/test_api.py`:

1. `GET /ai/health` → 200.
2. `POST /ai/chat` with a valid body → 200, `content-type: text/event-stream`.
3. A 6th request within a minute from the same `CF-Connecting-IP` → 429 — this is
   also the regression test that rate limiting reads the `CF-Connecting-IP` header
   and not the socket address (§Security).
4. Empty `messages` → 422.
5. A message longer than `MAX_INPUT_CHARS` → 422.

## 13. 4b — Acceptance criteria

- [ ] Discovered MCP tool set at startup matches the 4a allowlist exactly (7 names)
      — asserted at startup or in CI, not just checked manually
- [ ] A real end-to-end question ("Which rooms are there?") returns a streamed
      answer that used `get_rooms`, verified against the live 1b MCP endpoint
      (Docker network only)
- [ ] Rate limiting keys on `CF-Connecting-IP` behind the Cloudflare tunnel,
      verified in production
- [ ] LLM output is rendered as plain text/markdown on the frontend, never via
      `dangerouslySetInnerHTML` (verified in code review)
- [ ] Anthropic API key present only in `.env.prod`; startup fails fast with a
      clear log line (not a raw exception dump) if it's unset
- [ ] All tests green (existing 1b tests + 4a MCP tests + new 4b tests); CI green;
      merged via PR

## 14. Build order

4a was built on branch `feature/project4a-mcp`, one PR (merged). 4b: branch
`feature/project4b-ai-assistant`, one PR. Order: folder scaffold → `.env.example` →
MCP session + tool discovery → chat loop (§9) → FastAPI `/ai/*` routes → tests →
frontend `AiDashboard` tab → Docker/nginx wiring → deploy → prod acceptance checks
(§13). See `temp/stappen/stappen_project4.md` for the fully expanded phase list.
