# Project 3b — IoT Device Gateway (FastAPI + Kafka variant)

Secure gateway for IoT device registration, authentication, and message delivery.
Simulates the device layer of a production IoT platform — how physical sensors
authenticate and send data securely before it reaches the ingestion layer (Project 1).

This is the **implemented** variant of project 3; the AWS-native design is
specced in [project3a-iot-gateway.md](project3a-iot-gateway.md). Build contract,
phases, and acceptance criteria: [project3-prd.md](project3-prd.md).
Implementation: [`backend/project3b-iot-gateway/`](../backend/project3b-iot-gateway/).

## Implementation Variants

Like project 1/1b and 2a/2b, project 3 is designed in two variants — same security concept, different infrastructure:

| | AWS variant (3a) | FastAPI variant (3b) |
|---|---|---|
| Device auth | Cognito + API Gateway authorizer | Custom API keys — hashed in DynamoDB, validated via FastAPI `Depends()` |
| JWT | Issued by Cognito | `python-jose` — implemented in-house |
| Message queue | SQS | Kafka — Redpanda broker, `aiokafka` producer/consumer |
| Rate limiting | API Gateway built-in | Custom middleware in FastAPI |

**Chosen approach for 3b:** API keys per device. A device registers, receives a
generated key, and every request is validated via `Depends()`. Demonstrates
security thinking (hashing, least privilege, rate limiting) without a full auth
server. Fits the portfolio philosophy: don't overengineer, but demonstrate the
principle.

## Key Design Decisions

**Async as a design principle.** The gateway is built async from day one (`async def`
routes + async I/O). Rationale: an IoT gateway is the async use case par excellence — many devices
connecting at once and lots of concurrent small requests (I/O-bound). This deliberately
contrasts with project 1b, which stayed sync: at that load the threadpool is sufficient, and
rewriting it wouldn't yield any functional gain. In the gateway, though, the concurrency really
is inherent to the problem domain. (Project 4 uses async for a different reason: slow LLM I/O,
parallel tool calls, and streaming — see `project4-llm-mcp.md`.)

**Kafka as the message queue (decided 2026-07-04).** The queue slot is filled by
Kafka rather than Redis or a DB-backed queue:

- **Why Kafka:** it is the mirror of SQS in 3a — same role (decouple ingestion from
  processing, absorb bursts, survive consumer failures) but with the semantics that matter
  in data engineering: an append-only log with offsets, replayable by design, consumer
  groups for parallelism, and a `device_id` partition key that guarantees per-device
  ordering. It also completes the platform story: batch (Airflow, 2b), lakehouse
  (Databricks, 2c), and now streaming.
- **Why Redpanda as the broker:** Kafka-API-compatible, a single container, no JVM and no
  ZooKeeper — light enough to run permanently on acer-server next to the existing stack.
  The application code uses the plain Kafka protocol (`aiokafka`), so nothing is
  Redpanda-specific; the broker could be swapped for Apache Kafka or MSK unchanged.
- **Why `aiokafka`:** async producer/consumer matches the async-first design of the
  gateway (see above) — publishing to Kafka inside an `async def` route without blocking
  the event loop.
- **Flow:** gateway authenticates + validates a device message, produces it to the
  `sensor-events` topic (key = `device_id`), and returns `202 queued`. A separate consumer
  service (own container, consumer group `gateway-normalizer`) reads the topic, normalises
  the payload to the shared `prod-SensorEvents` contract, and writes to DynamoDB. This is
  exactly the "project 3 owns the data contract" role described in the root README: after
  3b, projects 1b and 2a consume one consistent format.
- **Topics:** `sensor-events` (device → platform) and `device-commands` (platform →
  device, polled by the simulator) — mirroring the two SQS queues in 3a.
- **DLQ pattern:** messages that fail normalisation are produced to
  `sensor-events.dlq` with the error attached — the Kafka equivalent of the SQS DLQ in 3a,
  and the same never-lose-data philosophy as the 2c quarantine table.

## Tech Stack

- **Runtime:** Python 3.12, FastAPI (async), Pydantic
- **Messaging:** Redpanda (Kafka API), `aiokafka`
- **Storage:** AWS DynamoDB (`p3-prod-Devices`)
- **Security:** bcrypt (API key hashes), `python-jose` (HS256 JWT)
- **Testing:** pytest, moto, mypy

## Architecture

```
simulate_device.py (N devices)
        │  API key → JWT
        ▼
Gateway (FastAPI, async) — auth, validation, rate limiting
        │  produce (key = device_id)
        ▼
Redpanda broker ── topic sensor-events ──► consumer service (aiokafka,
        │                                  group gateway-normalizer)
        │                                        │ normalise to shared contract
        │                                        ▼
        │                                  DynamoDB prod-SensorEvents
        └── topic sensor-events.dlq  ◄── records that fail normalisation
```

The gateway and broker are internal-only on the server (Docker `expose`, no
published ports) — devices are simulated in-network.

## API Endpoints

### POST /devices/register
Register a new IoT device. Returns an API key for subsequent authentication —
shown exactly once; only the bcrypt hash is stored.

```json
// Request
{
  "device_id": "sensor-001",
  "device_type": "temperature_sensor",
  "metadata": { "location": "conference-a1", "model": "DHT22" }
}

// Response 201
{
  "device_id": "sensor-001",
  "api_key": "p3-xxxxxxxxxxxxxxxx",
  "status": "registered"
}
```

### POST /devices/{device_id}/auth
Exchange API key for a short-lived JWT (1 hour).

```json
// Request
{ "api_key": "p3-xxxxxxxxxxxxxxxx" }

// Response 200
{ "access_token": "eyJ...", "expires_in": 3600, "token_type": "Bearer" }
```

### POST /messages
Send a sensor reading. Requires `Authorization: Bearer <token>`; the token's
device must match `device_id`.

```json
// Request
{
  "device_id": "sensor-001",
  "payload": { "temperature": 22.5, "humidity": 45 },
  "timestamp": "2026-01-07T10:30:00Z"
}

// Response 202
{ "message_id": "uuid", "status": "queued" }
```

### POST /commands/{device_id}
Send a command to a device (produced to `device-commands`, polled by the
simulator). Planned for phase 3b-3.

```json
// Request
{ "command": "update_interval", "parameters": { "interval_seconds": 60 } }

// Response 202
{ "command_id": "uuid", "status": "queued" }
```

### GET /devices/{device_id}/status
Get current device status and rate limit info. Requires a Bearer token.

```json
// Response 200
{
  "device_id": "sensor-001",
  "status": "online",
  "last_seen": "2026-01-07T10:30:00Z",
  "rate_limit_per_minute": 60,
  "rate_limit_remaining": 42
}
```

## DynamoDB Schema

**Devices table** (`p3-{env}-Devices`) — the only table; the 3a Messages table
is replaced by the Kafka topic, and rate-limit state lives in the gateway:
- PK: `device_id` (String)
- Attributes: `device_type`, `api_key_hash`, `status` (registered/online/offline/suspended), `metadata` (Map), `registered_at`, `last_seen`

## Infrastructure

Provisioned via CloudFormation
([`infrastructure/cloudformation.yaml`](../backend/project3b-iot-gateway/infrastructure/cloudformation.yaml)),
deployed by the `deploy-project3-infra.yml` GitHub Actions workflow: the
`p3-prod-Devices` table plus a least-privilege IAM user (`iot-gateway-app`,
GetItem/PutItem/UpdateItem on that table only). See the
[infrastructure README](../backend/project3b-iot-gateway/infrastructure/README.md)
for deploy, access-key rotation, and destroy procedures.

Runtime containers (Redpanda + gateway) are defined in the root
`docker-compose.prod.yml` and run permanently on acer-server.

## Rate Limiting

- Per-device sliding window (messages/minute), in-memory in the gateway
- Default 60/minute; configurable per device type in `config/rate_limits.yml`
- Exceeded limit → 429 Too Many Requests
- Documented limitation: in-memory state means single-instance only — scaling
  out would move this to a shared store (the 3a design shows the DynamoDB
  equivalent)

## Security

- API keys (`p3-` + 64 hex) stored as bcrypt hashes — never in plaintext, shown once at registration
- Short-lived HS256 JWTs (`python-jose`, 1 hour); `JWT_SECRET` only in `.env.prod` (chmod 600), gateway fails fast without it
- Token/device match enforced on `/messages` (403 on mismatch), suspended devices rejected
- Input validation via Pydantic on all endpoints; payload field cap (422)
- Kafka unavailable → 503 (fail closed, producer is non-fatal at startup)
- Least-privilege IAM: gateway credentials can only touch the Devices table

## Local Setup

```bash
cd backend/project3b-iot-gateway

# Local Redpanda + gateway
docker compose -f docker/docker-compose.yml up -d

# Install dependencies
pip install -r requirements-dev.txt

# Unit/API tests (moto — no AWS needed) + type check
pytest
mypy src
```

## Load Testing (locust — phase 3b-3)

Rate limiting is only credible if you can prove it. Load testing with locust demonstrates that:
- Device X gets blocked after X requests/minute (429 Too Many Requests)
- Other devices are unaffected by one device's behavior
- The gateway stays stable under burst traffic

### Scenarios

1. **Normal load** — 10 devices, each 1 request/second → all 200
2. **Rate limit hit** — 1 device sends 200 requests/minute → 429 past the threshold
3. **Burst isolation** — 1 device bombarded, 9 others unaffected → proves per-device isolation

This is the strongest argument for load testing in project 3 — not performance, but correctness of the rate limiting logic.
