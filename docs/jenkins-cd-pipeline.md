# Project 2b: Jenkins CD Pipeline

## Beschrijving

Declaratieve Jenkins CD pipeline voor project 2b (Behavior Pattern Analyzer). Automatiseert
het deployen van PySpark jobs, Airflow DAGs, en Terraform infrastructure, met environment
promotie (dev → staging → prod). Jenkins draait lokaal via Docker voor portfolio demonstratie.

**CI/CD splitsing (bewuste architectuurkeuze):**
- **CI** = GitHub Actions — linting, mypy, unit tests, terraform validate → snel, gratis,
  draait op elke push
- **CD** = Jenkins — terraform apply, DAG deploy, environment promotie → geeft controle over
  deployment gates en rollback

## Tech Stack

- **Orkestratie:** Jenkins LTS (declarative pipeline, Groovy DSL)
- **Containerization:** Docker + Docker Compose (Jenkins + agent)
- **Infra:** Terraform (RDS PostgreSQL + S3 + IAM)
- **Deploy:** Airflow CLI (DAG sync) + spark-submit (job validatie)
- **Secrets:** Jenkins Credentials Store (AWS keys, DB passwords)
- **Notificaties:** Jenkins e-mail + pipeline status badges

## Architectuur

```
Developer (git push)
        │
        ▼
GitHub Actions CI  ─── ruff, mypy, pytest unit, terraform validate
        │ groen?
        ▼
Jenkins CD Pipeline (lokaal via Docker)
        │
        ├── Stage 1: Checkout
        │   └── git clone / pull feature branch
        │
        ├── Stage 2: Unit Tests
        │   └── pytest tests/unit/ --cov-fail-under=80
        │
        ├── Stage 3: Terraform Plan
        │   ├── terraform init
        │   └── terraform plan -out=tfplan → opgeslagen als artifact
        │
        ├── Stage 4: Approval Gate  ◀── handmatige bevestiging vereist
        │   └── input("Deploy naar ${ENV}?")
        │
        ├── Stage 5: Terraform Apply
        │   └── terraform apply tfplan  (RDS PostgreSQL + S3 + IAM)
        │
        ├── Stage 6: DB Migratie
        │   └── python scripts/migrate.py  (raw_sensor_data, patterns, anomalies)
        │
        ├── Stage 7: Deploy Airflow DAGs
        │   └── airflow dags sync → behavior_pipeline beschikbaar in Airflow UI
        │
        ├── Stage 8: Smoke Test
        │   ├── airflow dags trigger behavior_pipeline --conf '{"days_back": 1}'
        │   └── airflow dags state behavior_pipeline → verwacht: success
        │
        └── Stage 9: Notify
            └── e-mail / console output met deployment samenvatting
```

## Pipeline Parameters

| Parameter | Default | Opties |
|-----------|---------|--------|
| `ENVIRONMENT` | `dev` | `dev`, `staging`, `prod` |
| `PIPELINE_ACTION` | `deploy` | `deploy`, `destroy` |
| `SKIP_TESTS` | `false` | `true`, `false` |
| `DRY_RUN` | `false` | `true`, `false` (plan alleen, geen apply) |
| `MIGRATE_DB` | `true` | `true`, `false` |

> **`destroy`** draait `terraform destroy` om RDS + S3 te verwijderen en kosten te stoppen.
> Zelfde patroon als project 2a — deploy wanneer nodig, destroy daarna.

## Directory Structuur

```
backend/project2b-behavior-analyzer/
├── Jenkinsfile                  ← declaratieve pipeline (hoofd-entrypoint)
├── docker/
│   └── docker-compose.yml       ← Jenkins LTS + Docker-in-Docker agent
├── scripts/
│   ├── migrate.py               ← DB schema aanmaken (idempotent)
│   ├── run_smoke_tests.sh       ← DAG trigger + status check
│   └── notify.sh                ← notificatie helperfunctie
├── shared-library/              ← Jenkins shared library (herbruikbare stappen)
│   └── vars/
│       ├── terraformPlan.groovy
│       ├── terraformApply.groovy
│       └── airflowDagSync.groovy
├── requirements-dev.txt         ← pytest, ruff, mypy (voor test stage in pipeline)
├── README.md
└── .env.example                 ← AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, etc.
```

## Jenkinsfile (structuur)

```groovy
pipeline {
    agent {
        docker {
            image 'python:3.12-slim'
            args '-v /var/run/docker.sock:/var/run/docker.sock'
        }
    }

    parameters {
        choice(name: 'ENVIRONMENT', choices: ['dev', 'staging', 'prod'])
        choice(name: 'PIPELINE_ACTION', choices: ['deploy', 'destroy'])
        booleanParam(name: 'DRY_RUN', defaultValue: false)
        booleanParam(name: 'MIGRATE_DB', defaultValue: true)
    }

    stages {
        stage('Checkout')       { steps { checkout scm } }

        // --- DEPLOY path ---
        stage('Unit Tests')     { when { expression { params.PIPELINE_ACTION == 'deploy' } }
                                  steps { sh 'pytest tests/unit/ --cov-fail-under=80' } }
        stage('TF Plan')        { when { expression { params.PIPELINE_ACTION == 'deploy' } }
                                  steps { sh 'terraform plan -out=tfplan' } }
        stage('Approval')       { steps { input "${params.PIPELINE_ACTION.capitalize()} naar ${params.ENVIRONMENT}?" } }
        stage('TF Apply')       { when { allOf {
                                      expression { params.PIPELINE_ACTION == 'deploy' }
                                      not { expression { params.DRY_RUN } }
                                  }}
                                  steps { sh 'terraform apply tfplan' } }
        stage('DB Migratie')    { when { allOf {
                                      expression { params.PIPELINE_ACTION == 'deploy' }
                                      expression { params.MIGRATE_DB }
                                  }}
                                  steps { sh 'python scripts/migrate.py' } }
        stage('Deploy DAGs')    { when { expression { params.PIPELINE_ACTION == 'deploy' } }
                                  steps { sh 'airflow dags sync' } }
        stage('Smoke Tests')    { when { expression { params.PIPELINE_ACTION == 'deploy' } }
                                  steps { sh 'scripts/run_smoke_tests.sh' } }

        // --- DESTROY path ---
        stage('TF Destroy')     { when { allOf {
                                      expression { params.PIPELINE_ACTION == 'destroy' }
                                      not { expression { params.DRY_RUN } }
                                  }}
                                  steps { sh 'terraform destroy -auto-approve' } }

        stage('Notify')         { steps { sh 'scripts/notify.sh' } }
    }

    post {
        always   { junit 'test-results/*.xml' }
        success  { echo 'Deployment geslaagd' }
        failure  { echo 'Deployment mislukt — rollback overwegen' }
    }
}
```

## Lokale Jenkins Setup

```bash
# Jenkins starten via Docker Compose
cd backend/project2b-behavior-analyzer/docker
docker compose up -d

# Jenkins bereikbaar via browser
open http://localhost:8080

# Initial admin password ophalen
docker exec jenkins-lts cat /var/jenkins_home/secrets/initialAdminPassword
```

## Secrets Configuratie (Jenkins Credentials Store)

Voeg toe via Jenkins UI → Manage Jenkins → Credentials:

| ID | Type | Beschrijving |
|----|------|--------------|
| `aws-access-key-id` | Secret text | AWS Access Key ID |
| `aws-secret-access-key` | Secret text | AWS Secret Access Key |
| `db-password-dev` | Secret text | PostgreSQL password (dev) |
| `db-password-prod` | Secret text | PostgreSQL password (prod) |

**Nooit** AWS credentials in de `Jenkinsfile` of environment files committen.

## Environment Promotie Strategie

```
feature branch → dev      (automatisch na CI groen)
dev → staging             (handmatige approval via Jenkins input step)
staging → prod            (handmatige approval + second-pair sign-off)
```

## Installatie & Gebruik

```bash
cd backend/project2b-behavior-analyzer

# 1. Jenkins starten
docker compose -f docker/docker-compose.yml up -d

# 2. Jenkins configureren (eerste keer)
#    - Installeer plugins: Pipeline, Docker Pipeline, Credentials Binding
#    - Voeg credentials toe (AWS keys, DB passwords)
#    - Maak pipeline job aan → koppel aan deze repository

# 3. Pipeline handmatig triggeren
#    Jenkins UI → Pipeline → Build with Parameters

# 4. Pipeline lokaal debuggen (zonder Jenkins)
terraform plan -out=tfplan
terraform apply tfplan
python scripts/migrate.py
airflow dags sync
bash scripts/run_smoke_tests.sh
```

## Testing

```bash
# Shared library Groovy stappen testen (unit)
cd shared-library
./gradlew test

# Script testen (bash)
bash -n scripts/run_smoke_tests.sh   # syntax check
bash -n scripts/notify.sh
```
