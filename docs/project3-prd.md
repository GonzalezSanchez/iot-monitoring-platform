# PRD — Project 3b: IoT Device Gateway (FastAPI + Kafka)

Build contract for project 3b. Base spec: [project3-iot-gateway.md](project3-iot-gateway.md)
(architecture, endpoints, Kafka decision). This PRD locks the decisions needed to build,
split into three phases — each with its own test contract and acceptance criteria,
following the 4a/4b pattern of [project4-prd.md](project4-prd.md).

Scope decision (2026-07-05): **only 3b is built now.** The AWS variant (3a — Cognito,
API Gateway authorizer, SQS, Lambda) stays fully specced in the base document as an
optional later variant.

## 1. Goal

A secure device gateway that owns the platform's ingestion contract: simulated IoT
devices register, authenticate (API key → short-lived JWT), and send sensor messages;
the gateway validates, rate-limits and produces them to Kafka; a consumer service
normalises every message to the shared `prod-SensorEvents` format. After 3b, projects
1b and 2a consume one consistent format — the gateway owns the data contract
(root README "Shared data contract" section).

## 2. Non-goals

- No 3a (AWS Cognito/SQS variant) — specced, not built.
- No frontend tab — project 3 is backend-only (README + screenshots are the demo).
- No real device hardware, no MQTT — HTTP devices simulated by `simulate_device.py`.
- No multi-instance gateway — single container; the in-memory rate limiter documents
  this limitation explicitly (a shared store is the 3a/DynamoDB pattern).
- No schema registry / Avro — JSON messages; versioning via a `schema_version` field.

## 3. Architecture & services

```
simulate_device.py (N devices, container)
        │  1. POST /devices/register      → api_key (returned once)
        │  2. POST /devices/{id}/auth     → JWT (1 h)
        │  3. POST /messages (Bearer JWT) → 202 {status: queued}
        ▼
gateway container (FastAPI, async, :8002)
        │  aiokafka producer — topic sensor-events, key = device_id
        ▼
Redpanda container (single node, internal Docker network only)
        │
        ▼
consumer container (aiokafka, group gateway-normalizer)
        │  normalise → shared contract
        ├─ OK   → DynamoDB prod-SensorEvents + prod-RoomStatus refresh
        └─ FAIL → topic sensor-events.dlq (original message + error field)
```

New directory `backend/project3-iot-gateway/` with `src/gateway/` (FastAPI app),
`src/consumer/` (normalizer), `scripts/simulate_device.py`, shared `src/common/`
(models, kafka config). One Docker image per service (gateway, consumer), both
non-root, same pattern as project 4b.

## 4. Kafka design (locked)

| Item | Decision |
|---|---|
| Broker | Redpanda, single container, no JVM/ZooKeeper — light enough for acer-server |
| Client | `aiokafka` (async, matches the gateway's async-first design) |
| Topics | `sensor-events` (1 partition, replication 1), `sensor-events.dlq`, `device-commands` |
| Partition key | `device_id` — per-device ordering guaranteed |
| Consumer group | `gateway-normalizer` |
| Delivery | At-least-once; consumer writes are idempotent (deterministic sort key per message) |
| Retention | 7 days on `sensor-events`, 30 days on the DLQ (never silently lost) |
| Exposure | `expose` only — Redpanda is never reachable from outside the Docker network |

The topic replaces the 3a `Messages` DynamoDB table — the Kafka log *is* the message
store. Only `p3-prod-Devices` is a new table.

## 5. Security requirements

1. **API keys**: generated server-side (`p3-` prefix + 32 random hex), returned exactly
   once at registration, stored only as **bcrypt hash** in `p3-prod-Devices`.
2. **JWT**: `python-jose`, HS256, 1-hour expiry, claims `sub=device_id` + `exp`;
   signing secret from `.env.prod` (fail-fast at startup if missing, like 4b).
3. **Rate limiting per device** (not per IP): sliding window in gateway memory,
   default 60 messages/min per device (`config/rate_limits.yml` per device type),
   429 on exceed. Documented single-instance limitation.
4. **Validation**: Pydantic on every endpoint; oversized payloads rejected (422);
   unknown device_id in JWT → 401.
5. **Suspension**: `status=suspended` in Devices table blocks auth and messages (403).
6. **Least privilege**: gateway container gets Kafka + Devices-table credentials only;
   consumer container gets Kafka + SensorEvents/RoomStatus credentials only.
7. Standing rules: `.env.prod` chmod 600 on the server, no secrets in git, generic
   error responses (never internal details).

## 6. API surface

Endpoints exactly as in the base spec: `POST /devices/register`,
`POST /devices/{device_id}/auth`, `POST /messages`, `POST /commands/{device_id}`,
`GET /devices/{device_id}/status`, plus `GET /health` (gateway + Kafka connectivity).
Request/response bodies: see base spec — they are the contract, changes require a PRD update.

## 7. Phases

### 3b-1 — Gateway + security core

Deliverables: FastAPI gateway (register/auth/messages/status/health), bcrypt + JWT flow,
per-device rate limiter, aiokafka producer, Redpanda in local + prod compose.

Test contract (pytest, no network — fake producer, moto for DynamoDB):
- register returns a key once and stores only a hash; second register for same id → 409
- auth: valid key → JWT; wrong key → 401; suspended device → 403
- messages: valid JWT → 202 and producer called with key=device_id; expired/garbage JWT → 401
- rate limit: device A blocked at limit+1 (429) while device B still passes (isolation)
- validation: oversized payload / missing fields → 422

Acceptance: gateway live on acer-server, `POST /messages` round-trip lands on the topic
(verified with `rpk topic consume`), `/health` shows kafka connected, all env files 600.

### 3b-2 — Consumer + data contract

Deliverables: normalizer service (consumer group `gateway-normalizer`), mapping
device payload → shared `prod-SensorEvents` format (the format project 1b writes),
`prod-RoomStatus` refresh, DLQ producer for failed normalisation, idempotent writes.

Test contract:
- valid message → exactly the shared-contract item shape (golden test against a 1b-written item)
- malformed payload → DLQ message with original + error, nothing written to DynamoDB
- duplicate delivery (same message twice) → single item (idempotency)
- unknown room/device mapping → DLQ, not dropped

Acceptance: end-to-end on the server — simulator message appears in `prod-SensorEvents`
via the gateway and shows up in the live dashboard (1b reads it); a poisoned message
lands in `sensor-events.dlq` and is inspectable.

### 3b-3 — Simulator + proof

Deliverables: `simulate_device.py` (N devices, configurable rate, registers itself,
refreshes JWT), locust load-test scenarios from the base spec (normal load / rate-limit
hit / burst isolation), README with architecture + screenshots (rpk topic describe,
locust report, DLQ inspection), CI job (`test-project3b`), root README section.

Acceptance = the three locust scenarios pass as specced: correct 429 behaviour, no
cross-device impact, gateway stable under burst. Optional afterwards: `device-commands`
polling in the simulator.

## 8. Operations & cost

- Redpanda + gateway + consumer join `docker-compose.prod.yml`; images via ghcr like
  all other services; deploy = `git pull` + `docker compose up -d` (server tracks main).
- Simulator runs on-demand (demos, acceptance runs) — not 24/7; DynamoDB stays
  PAY_PER_REQUEST (cents/month at demo volumes). Redpanda idle footprint ~0.5 GB RAM —
  verify server headroom before enabling (`free -h`), else cap with container memory limit.
- Monitoring: `/health` endpoints + container logs; Redpanda metrics endpoint is a
  future extension (could feed the existing OTel Collector → Grafana Cloud).

## 9. Build order

1. PRD merged (this document)
2. 3b-1 gateway — branch `feature/project3b-gateway`
3. 3b-2 consumer — branch `feature/project3b-consumer`
4. 3b-3 simulator + load tests + docs — branch `feature/project3b-simulator`

One phase = one PR, user merges, deploy to server, acceptance checked before the next
phase starts — same rhythm as project 4.
