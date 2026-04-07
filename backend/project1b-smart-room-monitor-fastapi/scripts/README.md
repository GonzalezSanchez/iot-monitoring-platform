# Scripts — Smart Room Monitor (Project 1b)

Utility scripts for local development setup and production data seeding.

---

## Overview

| Script | Purpose | Environment |
|--------|---------|-------------|
| `create_tables_local.py` | Create both DynamoDB tables in DynamoDB Local | Local only |
| `add_test_room_local.py` | Insert a single demo room into DynamoDB Local | Local only |
| `seed_prod_data.py` | Populate production DynamoDB with realistic demo data | Production |

---

## Execution Order (first-time setup)

### Local development
1. Start DynamoDB Local: `docker compose up`
2. `create_tables_local.py` — creates `dev-RoomStatus` and `SensorEvents` tables
3. `add_test_room_local.py` — seeds a demo room so the dashboard is not empty
4. Start the API: `uvicorn main:app --reload`

### Production
1. Deploy CloudFormation stack — creates `prod-RoomStatus` and `prod-SensorEvents`
2. Create `.env.prod` with AWS credentials
3. `seed_prod_data.py` — seeds 4 realistic rooms with different statuses

---

## Scripts

### `create_tables_local.py`

Creates both DynamoDB tables in DynamoDB Local (port 8001).
Safe to run multiple times — skips tables that already exist.

**Prerequisites:** DynamoDB Local running (`docker compose up`)

```bash
cd backend/project1b-smart-room-monitor-fastapi
python scripts/create_tables_local.py
```

---

### `add_test_room_local.py`

Inserts a single demo room (`conference-a1`) into the local `dev-RoomStatus` table.

**Prerequisites:** DynamoDB Local running, tables created (`create_tables_local.py`)

```bash
python scripts/add_test_room_local.py
```

---

### `seed_prod_data.py`

Populates production DynamoDB with 4 realistic demo rooms:
- **Conference Room A1** — active, normal readings
- **Conference Room B2** — warning (high temperature)
- **Meeting Room C3** — active, empty
- **Lab D4** — alert (critical temperature + humidity)

**Prerequisites:** `.env.prod` must exist with valid AWS credentials

```bash
cd backend/project1b-smart-room-monitor-fastapi
python scripts/seed_prod_data.py
```
