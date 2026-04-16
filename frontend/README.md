# IoT Monitoring Platform — Frontend

React dashboard for the IoT Monitoring Platform. Connects to the project 1b FastAPI backend and the project 2a Behavior Analyzer API.

## Stack

- **React 19** — UI framework
- **Vite 8** — build tool and dev server
- **Tailwind CSS v4** — styling
- **Node 22 LTS** — runtime

## Local Development

### Prerequisites

- [nvm](https://github.com/nvm-sh/nvm) installed
- Docker (for DynamoDB Local and project 2a PostgreSQL)
- conda environment `iot-smart-fastapi` for project 1b backend

### 1. Use the correct Node version

```bash
nvm use
```

### 2. Install dependencies

```bash
npm install
```

### 3. Start DynamoDB Local (project 1b)

```bash
cd ../backend/project1b-smart-room-monitor-fastapi
docker compose -f docker/docker-compose.yml up -d
python scripts/create_tables_local.py
python scripts/add_test_room_local.py
```

### 4. Start the FastAPI backend (project 1b)

```bash
conda activate iot-smart-fastapi
PYTHONPATH=src uvicorn src.main:app --reload --port 8000
```

### 5. Start the frontend dev server

```bash
cd frontend
npm start
```

Open [http://localhost:5173](http://localhost:5173).

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `VITE_API_ENDPOINT` | Project 1b FastAPI URL | empty (nginx proxy in production) |
| `VITE_P2A_API_ENDPOINT` | Project 2a Behavior Analyzer API URL | empty (not deployed by default) |

> Project 2a is deployed on-demand. If `VITE_P2A_API_ENDPOINT` is not set, the Behavior Analyzer tab shows a "not deployed" message.

All `.env` files are gitignored. In production, variables are injected as Docker build args via GitHub Actions secrets (`VITE_API_ENDPOINT`, `VITE_P2A_API_ENDPOINT`). After each `terraform destroy` + `deploy`, update the `VITE_P2A_API_ENDPOINT` secret in GitHub with the new API Gateway URL and trigger a new Docker build.

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   └── ProjectTabs.jsx       # Tab navigation
│   ├── pages/
│   │   ├── RoomDashboard.jsx     # Project 1b — Smart Room Monitor
│   │   └── BehaviorDashboard.jsx # Project 2a — Behavior Analyzer
│   ├── hooks/                    # Custom React hooks
│   ├── App.jsx                   # Root component, tab routing
│   ├── index.jsx                 # React entry point
│   └── index.css                 # Tailwind import
├── .nvmrc                        # Node version (22)
├── vite.config.js
└── package.json
```

## Production Build

```bash
npm run build
```

Built files go to `dist/`. In production, nginx serves the static files and proxies API calls to the FastAPI backend.
