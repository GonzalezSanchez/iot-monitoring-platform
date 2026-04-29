# Stappen: Observability implementatie project 1b

OpenTelemetry + Datadog voor de FastAPI backend op de home server.

## Architectuur

```
FastAPI (opentelemetry-instrument uvicorn)
  → OTLP gRPC (port 4317)
    → OTel Collector (Docker: otel/opentelemetry-collector-contrib)
      → Datadog Exporter → datadoghq.eu
```

Waarom OTel Collector als tussenlaag:
- Backend stuurt vendor-neutral OTLP — geen vendor lock-in in de code
- Collector is de enige plek met de Datadog API key
- Na Datadog trial: alleen `otel-collector-config.yaml` wijzigen naar Grafana Stack (Tempo + Loki + Prometheus), geen code-aanpassingen

## Gewijzigde bestanden

| Bestand | Wat |
|---|---|
| `requirements.txt` | `opentelemetry-distro` + `opentelemetry-exporter-otlp-proto-grpc` |
| `Dockerfile` | `opentelemetry-bootstrap -a install` + CMD via `opentelemetry-instrument` |
| `otel-collector-config.yaml` | Collector config: OTLP ontvangen → Datadog exporteren |
| `docker-compose.prod.yml` | otel-collector service toegevoegd; alle services via `env_file` |
| `.env.example` | DD_API_KEY + OTel vars gedocumenteerd |

## Stap 1: requirements.txt

```
opentelemetry-distro>=0.44b0
opentelemetry-exporter-otlp-proto-grpc>=1.23.0
```

`opentelemetry-distro` bevat de `opentelemetry-bootstrap` CLI die automatisch alle relevante instrumentaties detecteert en installeert (FastAPI, boto3, logging, ...).

## Stap 2: Dockerfile

```dockerfile
RUN pip install --no-cache-dir -r requirements.txt && \
    opentelemetry-bootstrap -a install

CMD ["opentelemetry-instrument", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`opentelemetry-instrument` wikkelt uvicorn in — geen enkele regel in `main.py` hoeft te wijzigen.

## Stap 3: OTel Collector config (`otel-collector-config.yaml`)

- Receivers: OTLP gRPC (4317) + HTTP (4318)
- Processors: batch met 10s flush interval (efficiëntie, niet blocking voor de app)
- Exporters: datadog met `site: datadoghq.eu`
- Pipelines: traces + metrics + logs

## Stap 4: docker-compose.prod.yml

Alle services gebruiken `env_file` — geen `environment:` blok. Eén bestand, alle vars.

```yaml
otel-collector:
  env_file:
    - ./backend/project1b-smart-room-monitor-fastapi/.env.prod

backend:
  env_file:
    - ./backend/project1b-smart-room-monitor-fastapi/.env.prod
```

## Stap 5: `.env.prod` aanvullen op de home server

Voeg toe aan het bestaande `.env.prod`:

```bash
# Datadog
DD_API_KEY=<jouw_api_key_van_datadoghq.eu>

# OpenTelemetry
OTEL_SERVICE_NAME=iot-smart-room-monitor
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_TRACES_EXPORTER=otlp
OTEL_METRICS_EXPORTER=otlp
OTEL_LOGS_EXPORTER=otlp
OTEL_PYTHON_LOG_CORRELATION=true
OTEL_EXPORTER_OTLP_TIMEOUT=3000
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=production,service.version=1.0.0
```

## Stap 6: Lokaal testen vóór push

Test de instrumentatie-laag lokaal zonder collector of Datadog:

```bash
pip install opentelemetry-distro opentelemetry-exporter-otlp-proto-grpc
opentelemetry-bootstrap -a install

cd backend/project1b-smart-room-monitor-fastapi
OTEL_TRACES_EXPORTER=console OTEL_METRICS_EXPORTER=none OTEL_LOGS_EXPORTER=none \
  opentelemetry-instrument uvicorn src.main:app --host 0.0.0.0 --port 8000
```

In een tweede terminal:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/rooms
```

Als spans in JSON formaat verschijnen in de eerste terminal → instrumentatie werkt → veilig om te pushen.

## Stap 7: Deploy op de home server

```bash
git pull
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --build

# Logs controleren
docker compose -f docker-compose.prod.yml logs -f otel-collector
docker compose -f docker-compose.prod.yml logs -f backend
```

## Stap 8: Verifiëren in Datadog UI

```bash
# Requests genereren zodat traces zichtbaar zijn
curl https://iot.gonzalezsanchez.dev/health
curl https://iot.gonzalezsanchez.dev/rooms
curl https://iot.gonzalezsanchez.dev/events
```

Screenshots voor portfolio:
- [ ] APM → Services → `iot-smart-room-monitor`
- [ ] APM → Traces → flame graph van POST /events (toont FastAPI span + DynamoDB child span)
- [ ] Latency/throughput overzicht
- [ ] Logs met trace ID correlatie

## Troubleshooting

**Collector start niet:**
```bash
docker compose -f docker-compose.prod.yml logs otel-collector
# DD_API_KEY aanwezig in .env.prod? Site datadoghq.eu? Config YAML syntax?
```

**Geen traces in Datadog (collector draait wel):**
```bash
# Controleer of backend de collector bereikt
docker compose -f docker-compose.prod.yml logs backend | grep -i otel
# Collector en backend zitten in hetzelfde Docker network → http://otel-collector:4317 werkt
```

**Belangrijk:** gebruik altijd `otel/opentelemetry-collector-contrib` (niet `otel/opentelemetry-collector`) — de contrib variant bevat de Datadog exporter.

## Na Datadog trial: overstap naar Grafana Stack

Alleen `otel-collector-config.yaml` wijzigt — geen code-aanpassingen:

```yaml
exporters:
  otlp/tempo:
    endpoint: http://tempo:4317
  loki:
    endpoint: http://loki:3100/loki/api/v1/push
  prometheus:
    endpoint: 0.0.0.0:8889
```

FastAPI code, Dockerfile, requirements.txt: **ongewijzigd**.
