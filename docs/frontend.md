# Frontend — React Dashboard

## Overview

Real-time dashboard for visualising IoT sensor data and room states.
Serves as the UI layer for the backend projects in this portfolio.

**Live:** [iot.gonzalezsanchez.dev](https://iot.gonzalezsanchez.dev)

---

## Stack

| Tool | Purpose |
|------|---------|
| React 18 | UI framework |
| Vite | Build tool and dev server |
| nginx | Static file serving in production |
| Docker | Containerised deployment |

---

## Architecture

```
Browser
   │
   ▼
nginx (port 80 inside container, 3000 on host)
   │
   ▼
React SPA (built with Vite)
   │
   ├── ProjectTabs       — tab navigation (Smart Room Monitor / Behavior Analyzer / IoT Gateway)
   │
   └── RoomDashboard     — main page
         ├── SendEventForm     — send a sensor event to POST /events
         ├── RoomCard          — displays room status and current sensor readings
         └── EventRow          — displays individual sensor events in a table
```

---

## Features

**Smart Room Monitor tab:**
- Lists all rooms with current sensor state (temperature, humidity, occupancy, motion)
- Room cards colour-coded by status: normal (green), warning (amber), alert (red), offline (grey)
- Click a room to expand its event history
- Send Sensor Event form — POST a sensor event directly from the UI (useful for demos)
- Auto-refreshes every 30 seconds

**Behavior Analyzer tab:** coming soon (Project 2a)

**IoT Gateway tab:** coming soon (Project 3)

---

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `VITE_API_ENDPOINT` | Backend API base URL | `https://iot.gonzalezsanchez.dev` |

Set in `.env` for local development. In production, injected at build time via Docker build args or `.env.production`.

---

## Running Locally

```bash
cd frontend
npm install
npm run dev        # starts dev server at http://localhost:5173
```

The app expects the FastAPI backend to be running. Set `VITE_API_ENDPOINT` in `.env`:
```
VITE_API_ENDPOINT=http://localhost:8000
```

---

## Deployment

Built as a static site and served via nginx inside a Docker container.

```bash
# Build and run locally
docker build -t iot-frontend .
docker run -p 3000:80 iot-frontend
```

In production, the image is built and pushed to `ghcr.io/gonzalezsanchez/iot-frontend:latest`
by GitHub Actions on every push to `develop` or `main`.

To update the server after a new image is pushed:
```bash
git pull
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

---

## Project Structure

```
frontend/
├── src/
│   ├── App.jsx                  — root component, tab routing
│   ├── index.jsx                — entry point
│   ├── components/
│   │   └── ProjectTabs.jsx      — tab navigation bar
│   └── pages/
│       └── RoomDashboard.jsx    — Smart Room Monitor page
├── Dockerfile                   — multi-stage build (node → nginx)
├── nginx.conf                   — nginx config for SPA routing
├── package.json
└── vite.config.js
```
