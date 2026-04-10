# Project 2b: Behavior Pattern Analyzer (Data Engineering Stack)

## Beschrijving

Dezelfde analytics als Project 2a — gedragspatronen en anomalieën detecteren uit
sensordata — maar nu geïmplementeerd met een data engineering stack. Een bewuste
herhaling om te demonstreren dat dezelfde businesslogica met andere tools oplosbaar is.

**Vergelijking met Project 2a:**

| Aspect | Project 2a (AWS native) | Project 2b (Data Engineering) |
|--------|------------------------|-------------------------------|
| Orkestratie | AWS Step Functions | Apache Airflow |
| Processing | Python (pandas) | PySpark (gedistribueerd) |
| Infra | Terraform + Aurora Serverless v2 | Terraform + RDS PostgreSQL |
| Visualisatie | REST API | Power BI rapport |
| AI interface | — | RAG bot (LLM + pgvector) |
| CD | — | Jenkins (dev → staging → prod) |

## Tech Stack

- **Orkestratie:** Apache Airflow 2.x (Docker via officieel `apache/airflow` image)
- **Processing:** PySpark 3.x (Spark SQL + MLlib voor patroondetectie)
- **Database:** RDS PostgreSQL (`db.t3.micro` op AWS; lokaal via Docker) + pgvector extensie
- **Opslag:** S3 (ruwe sensor events als Parquet bestanden)
- **Visualisatie:** Power BI Desktop (DirectQuery op PostgreSQL)
- **LLM / RAG:** OpenAI API (of Ollama lokaal) + pgvector voor semantisch zoeken over patronen en anomalieën
- **Infra:** Terraform
- **CI:** GitHub Actions (ruff, mypy, pytest, terraform validate)
- **CD:** Jenkins (declaratief, lokaal via Docker — zie [docs/jenkins-cd-pipeline.md](jenkins-cd-pipeline.md))

## Architectuur

```
S3 (sensor events als Parquet)
        │
        ▼ (via Airflow DAG: @weekly)
┌────────────────────────────────────────────────────┐
│  Airflow DAG: behavior_pipeline                    │
│                                                    │
│  extract_task → transform_task → analyze_task      │
└────────────────────────────────────────────────────┘
        │              │              │
        ▼              ▼              ▼
  PySpark Job:   PySpark Job:   PySpark Job:
  Extract        Transform      Analyze
  (Parquet       (normalize,    (Spark SQL +
   → JDBC)        validate)      MLlib)
        │
        ▼
  RDS PostgreSQL
  ├── raw_sensor_data
  ├── patterns
  └── anomalies
        │
        ▼
  Power BI rapport
  (DirectQuery)
```

## Database Schema (PostgreSQL)

Zelfde schema als Project 2a — opzettelijk, om portabiliteit te demonstreren.

**raw_sensor_data:**
```sql
CREATE TABLE raw_sensor_data (
    id UUID PRIMARY KEY,
    entity_id VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    data JSONB NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_rsd_entity_timestamp ON raw_sensor_data (entity_id, timestamp);
CREATE INDEX idx_rsd_processed ON raw_sensor_data (processed);
```

**patterns:**
```sql
CREATE TABLE patterns (
    id UUID PRIMARY KEY,
    entity_id VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    pattern_type VARCHAR(100) NOT NULL,
    confidence DECIMAL(3,2) NOT NULL,
    pattern_data JSONB NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_patterns_entity ON patterns (entity_id, entity_type);
```

**anomalies:**
```sql
CREATE TABLE anomalies (
    id UUID PRIMARY KEY,
    entity_id VARCHAR(100) NOT NULL,
    anomaly_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    details JSONB NOT NULL,
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_anomalies_entity_timestamp ON anomalies (entity_id, timestamp);
CREATE INDEX idx_anomalies_resolved ON anomalies (resolved);
```

## PySpark Jobs

### Extract (`jobs/extract.py`)
- Leest Parquet bestanden van S3 (of lokale MinIO emulatie)
- Schrijft rijen naar `raw_sensor_data` via JDBC (PostgreSQL)
- Idempotent: `INSERT ... ON CONFLICT DO NOTHING` via Spark JDBC mode `"ignore"`

### Transform (`jobs/transform.py`)
- Leest `raw_sensor_data` waar `processed = FALSE`
- Filtert ongeldige sensorwaarden (null, buiten bereik)
- Normaliseert eenheden (Fahrenheit → Celsius, etc.)
- Markeert rijen als `processed = TRUE`

### Analyze (`jobs/analyze.py`)
- **Patroondetectie via Spark SQL:**
  - `occupancy_schedule`: window functions per uur per dag → mediaan bezetting
  - `temperature_trend`: lineaire regressie via `pyspark.ml.regression.LinearRegression`
- **Anomaliedetectie:**
  - z-score berekening: `(value - mean) / stddev` via Spark SQL aggregates
  - z-score ≥ 3 → anomalie geschreven naar `anomalies`

## Airflow DAG

```python
# dags/behavior_pipeline.py
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

with DAG(
    dag_id="behavior_pipeline",
    schedule="0 2 * * 1",          # elke maandag 02:00
    start_date=datetime(2026, 1, 1),
    catchup=False,
    params={"days_back": 7},
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
) as dag:
    extract  = BashOperator(task_id="extract",  bash_command="spark-submit jobs/extract.py")
    transform= BashOperator(task_id="transform",bash_command="spark-submit jobs/transform.py")
    analyze  = BashOperator(task_id="analyze",  bash_command="spark-submit jobs/analyze.py")

    extract >> transform >> analyze
```

## RAG Interface (LLM + Semantic Search)

Na afloop van het data engineering gedeelte wordt een RAG (Retrieval-Augmented Generation)
interface toegevoegd die natuurlijke taal queries mogelijk maakt over de gedetecteerde
patronen en anomalieën in PostgreSQL.

**Waarom hier?** De patterns en anomalies tabellen bevatten beschrijvende tekst
(`pattern_type`, `anomaly_type`, `details`). Dat is een natuurlijke kandidaat voor
semantisch zoeken: een gebruiker vraagt *"Welke anomalieën waren er vorige week in kamer A?"*
en het systeem zoekt via embeddings in plaats van exacte SQL-match.

**Architectuur:**
```
Gebruiker (vraag in natuurlijke taal)
        │
        ▼
  RAG bot (Python)
        │
        ├── 1. Embed de vraag (OpenAI text-embedding of Ollama lokaal)
        ├── 2. Semantisch zoeken in pgvector (cosine similarity op pattern/anomaly beschrijvingen)
        ├── 3. Top-k resultaten als context meegeven aan LLM
        └── 4. LLM genereert antwoord (GPT-4 of open source via Ollama)
```

**Componenten:**
- `pgvector` PostgreSQL extensie — opslaan van embedding vectoren naast bestaande data
- `jobs/embed_patterns.py` — Airflow task die na Analyze draait: embeds `pattern_data` en `details`
  kolommen en schrijft vectoren naar PostgreSQL via pgvector
- `rag/bot.py` — RAG query interface:
  ```python
  from openai import OpenAI
  import psycopg2

  def query(question: str) -> str:
      embedding = client.embeddings.create(input=question, model="text-embedding-3-small")
      # pgvector nearest neighbour
      rows = db.execute(
          "SELECT details FROM anomalies ORDER BY embedding <=> %s LIMIT 5",
          (embedding.data[0].embedding,)
      )
      context = "\n".join(r[0] for r in rows)
      return client.chat.completions.create(
          model="gpt-4o-mini",
          messages=[
              {"role": "system", "content": "Je bent een IoT data analist."},
              {"role": "user", "content": f"Context:\n{context}\n\nVraag: {question}"}
          ]
      ).choices[0].message.content
  ```
- Prompt injection preventie: context wordt gesaniteerd voor het aan de LLM meegegeven wordt
- Lokaal alternatief: Ollama (`ollama run llama3`) — geen API kosten

**Technieken uit de LinkedIn Learning cursus (LLMs + Prompt Engineering):**
- Semantic search met cross-encoders
- RAG bot bouwen
- Prompt chaining + input/output validatie
- Prompt injection attacks voorkomen
- Chain-of-thought prompting voor anomalie uitleg

---

## Power BI Rapport

- **Verbinding:** DirectQuery op PostgreSQL (`patterns` + `anomalies` tabellen)
- **Pagina's:**
  - Overzicht — patroon frequentie per kamer per week (bar chart)
  - Anomalieën — severity heatmap per kamer (matrix visualisatie)
  - Temperatuurtrend — lijndiagram met confidence band
- **Bestand:** `reports/behavior_analyzer.pbix` (gitignored — te groot voor Git)
- **Screenshot:** opgenomen in README voor portfolio presentatie

## Lokale Setup

```bash
cd backend/project2b-behavior-analyzer

# 1. Alle services starten (Airflow + PostgreSQL + MinIO + Spark)
docker compose -f docker/docker-compose.yml up -d

# 2. DB migratie draaien
python scripts/migrate.py

# 3. Airflow bereikbaar op http://localhost:8090
#    (port 8090 om conflict met project 1b te vermijden)

# 4. MinIO (S3 lokaal) bereikbaar op http://localhost:9001
#    credentials: minioadmin / minioadmin

# 5. DAG manueel triggeren
airflow dags trigger behavior_pipeline --conf '{"days_back": 7}'

# 6. Of PySpark job direct draaien (zonder Airflow)
spark-submit --master local[*] jobs/extract.py
spark-submit --master local[*] jobs/transform.py
spark-submit --master local[*] jobs/analyze.py
```

## Testing

```bash
# Unit tests (geen echte DB of Spark vereist)
pytest tests/unit/ -v --cov=jobs --cov=dags --cov-fail-under=80

# Integratie tests (vereist Docker services)
docker compose -f docker/docker-compose.yml up -d
pytest tests/integration/ -v --no-cov

# Linting + type checking
ruff check jobs/ dags/ scripts/
mypy jobs/ dags/
```

## CI/CD

- **CI:** GitHub Actions — ruff, mypy, pytest unit, terraform validate (bij elke push)
- **CD:** Jenkins declaratieve pipeline — packaging, terraform apply, environment promotie
  - Dev → staging: handmatige approval in Jenkins UI
  - Staging → prod: handmatige approval + second sign-off
  - Zie [docs/jenkins-cd-pipeline.md](jenkins-cd-pipeline.md) voor Jenkins setup

## Directory Structuur

```
backend/project2b-behavior-analyzer/
├── dags/
│   └── behavior_pipeline.py     ← Airflow DAG definitie
├── jobs/
│   ├── extract.py               ← PySpark: S3 Parquet → PostgreSQL
│   ├── transform.py             ← PySpark: normalize + validate
│   └── analyze.py               ← PySpark: patronen + anomalieën
├── infrastructure/
│   ├── main.tf                  ← RDS PostgreSQL + S3 + IAM
│   ├── variables.tf
│   └── outputs.tf
├── scripts/
│   ├── migrate.py               ← DB schema aanmaken
│   └── seed_data.py             ← testdata genereren (Parquet naar MinIO)
├── tests/
│   ├── unit/
│   │   ├── test_extract.py
│   │   ├── test_transform.py
│   │   ├── test_analyze.py
│   │   └── test_dag.py
│   └── integration/
│       └── test_pipeline.py
├── reports/                     ← Power BI .pbix (gitignored)
├── docker/
│   └── docker-compose.yml       ← Airflow + PostgreSQL + MinIO + Spark
├── Jenkinsfile                  ← CD pipeline
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── README.md
```
