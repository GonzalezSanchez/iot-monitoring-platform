# Project 2b: Jenkins CD Pipeline

## Beschrijving

Declaratieve Jenkins CD pipeline voor de volledige IoT monitoring platform. Automatiseert
het verpakken van Lambda code, Terraform planning + deployment, en environment promotie
(dev → staging → prod). Jenkins draait lokaal via Docker voor portfolio demonstratie.

**CI/CD splitsing (bewuste architectuurkeuze):**
- **CI** = GitHub Actions — linting, mypy, unit tests, terraform validate → snel, gratis,
  draait op elke push
- **CD** = Jenkins — packaging, terraform apply, environment promotie → geeft controle over
  deployment gates en rollback

## Tech Stack

- **Orkestratie:** Jenkins LTS (declarative pipeline, Groovy DSL)
- **Containerization:** Docker + Docker Compose (Jenkins + agent)
- **Infra:** Terraform (reeds aanwezig in project 2a)
- **Packaging:** Bash scripts (ZIP bundels voor Lambda functions)
- **Secrets:** Jenkins Credentials Store (AWS keys, DB passwords)
- **Notificaties:** Jenkins e-mail + pipeline status badges

## Architectuur

```
Developer (git push)
        │
        ▼
GitHub Actions CI  ─── ruff, mypy, pytest, terraform validate
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
        ├── Stage 3: Package Lambdas
        │   ├── zip lambdas/extract/ → dist/extract.zip
        │   ├── zip lambdas/transform/ → dist/transform.zip
        │   ├── zip lambdas/analyze/ → dist/analyze.zip
        │   └── zip lambdas/api/ → dist/api.zip
        │
        ├── Stage 4: Terraform Plan
        │   ├── terraform init
        │   └── terraform plan -out=tfplan → opgeslagen als artifact
        │
        ├── Stage 5: Approval Gate  ◀── handmatige bevestiging vereist
        │   └── input("Deploy naar ${ENV}?")
        │
        ├── Stage 6: Terraform Apply
        │   └── terraform apply tfplan
        │
        ├── Stage 7: Smoke Test
        │   └── curl endpoints → status 200 verwacht
        │
        └── Stage 8: Notify
            └── e-mail / console output met deployment samenvatting
```

## Pipeline Parameters

| Parameter | Default | Opties |
|-----------|---------|--------|
| `ENVIRONMENT` | `dev` | `dev`, `staging`, `prod` |
| `PROJECT` | `all` | `all`, `project1a`, `project2a` |
| `SKIP_TESTS` | `false` | `true`, `false` |
| `DRY_RUN` | `false` | `true`, `false` (plan alleen, geen apply) |

## Directory Structuur

```
backend/project2b-jenkins-cd/
├── Jenkinsfile                  ← declaratieve pipeline (hoofd-entrypoint)
├── docker/
│   └── docker-compose.yml       ← Jenkins LTS + Docker-in-Docker agent
├── scripts/
│   ├── package_lambdas.sh       ← ZIP bundels bouwen voor alle Lambda's
│   ├── run_smoke_tests.sh       ← basis health checks na deployment
│   └── notify.sh                ← notificatie helperfunctie
├── shared-library/              ← Jenkins shared library (herbruikbare stappen)
│   └── vars/
│       ├── packageLambda.groovy
│       ├── terraformPlan.groovy
│       └── terraformApply.groovy
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
        booleanParam(name: 'DRY_RUN', defaultValue: false)
    }

    stages {
        stage('Checkout')     { steps { checkout scm } }
        stage('Unit Tests')   { steps { sh 'pytest tests/unit/ --cov-fail-under=80' } }
        stage('Package')      { steps { sh 'scripts/package_lambdas.sh' } }
        stage('TF Plan')      { steps { sh 'terraform plan -out=tfplan' } }
        stage('Approval')     { steps { input "Deploy naar ${params.ENVIRONMENT}?" } }
        stage('TF Apply')     { when { not { expression { params.DRY_RUN } } }
                                steps { sh 'terraform apply tfplan' } }
        stage('Smoke Tests')  { steps { sh 'scripts/run_smoke_tests.sh' } }
        stage('Notify')       { steps { sh 'scripts/notify.sh' } }
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
cd backend/project2b-jenkins-cd/docker
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
cd backend/project2b-jenkins-cd

# 1. Jenkins starten
docker compose -f docker/docker-compose.yml up -d

# 2. Jenkins configureren (eerste keer)
#    - Installeer plugins: Pipeline, Docker Pipeline, Credentials Binding
#    - Voeg credentials toe (AWS keys, DB passwords)
#    - Maak pipeline job aan → koppel aan deze repository

# 3. Pipeline handmatig triggeren
#    Jenkins UI → Pipeline → Build with Parameters

# 4. Pipeline lokaal debuggen (zonder Jenkins)
bash scripts/package_lambdas.sh
terraform plan -out=tfplan
terraform apply tfplan
```

## Testing

```bash
# Shared library Groovy stappen testen (unit)
# (Groovy unit tests via JenkinsPipelineUnit library)
cd shared-library
./gradlew test

# Script testen (bash)
bash -n scripts/package_lambdas.sh   # syntax check
bash -n scripts/run_smoke_tests.sh
```
