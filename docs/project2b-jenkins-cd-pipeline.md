# Project 2b: Jenkins CD Pipeline

## Description

Declarative Jenkins CD pipeline for project 2b (Behavior Pattern Analyzer). Automates
deployment of PySpark jobs, Airflow DAGs, and Terraform infrastructure, with environment
promotion (dev → staging → prod). Jenkins runs locally via Docker for portfolio demonstration.

**CI/CD split (deliberate architecture choice):**
- **CI** = GitHub Actions — linting, mypy, unit tests, terraform validate → fast, free,
  runs on every push
- **CD** = Jenkins — terraform apply, DAG deploy, environment promotion → provides control over
  deployment gates and rollback

## Tech Stack

- **Orchestration:** Jenkins LTS (declarative pipeline, Groovy DSL)
- **Containerization:** Docker + Docker Compose (Jenkins + agent)
- **Infra:** Terraform (RDS PostgreSQL + S3 + IAM)
- **Deploy:** Airflow CLI (DAG sync) + spark-submit (job validation)
- **Secrets:** Jenkins Credentials Store (AWS keys, DB passwords)
- **Notifications:** Jenkins email + pipeline status badges

## Architecture

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
        │   └── terraform plan -out=tfplan → saved as artifact
        │
        ├── Stage 4: Approval Gate  ◀── manual confirmation required
        │   └── input("Deploy to ${ENV}?")
        │
        ├── Stage 5: Terraform Apply
        │   └── terraform apply tfplan  (RDS PostgreSQL + S3 + IAM)
        │
        ├── Stage 6: DB Migration
        │   └── python scripts/migrate.py  (raw_sensor_data, patterns, anomalies)
        │
        ├── Stage 7: Deploy Airflow DAGs
        │   └── airflow dags sync → behavior_pipeline available in Airflow UI
        │
        ├── Stage 8: Smoke Test
        │   ├── airflow dags trigger behavior_pipeline --conf '{"days_back": 1}'
        │   └── airflow dags state behavior_pipeline → expected: success
        │
        └── Stage 9: Notify
            └── email / console output with deployment summary
```

## Pipeline Parameters

| Parameter | Default | Options |
|-----------|---------|--------|
| `ENVIRONMENT` | `dev` | `dev`, `staging`, `prod` |
| `PIPELINE_ACTION` | `deploy` | `deploy`, `destroy` |
| `SKIP_TESTS` | `false` | `true`, `false` |
| `DRY_RUN` | `false` | `true`, `false` (plan only, no apply) |
| `MIGRATE_DB` | `true` | `true`, `false` |

> **`destroy`** runs `terraform destroy` to remove RDS + S3 and stop costs.
> Same pattern as project 2a — deploy when needed, destroy afterward.

## Directory Structure

```
backend/project2b-behavior-analyzer/
├── Jenkinsfile                  ← declarative pipeline (main entrypoint)
├── docker/
│   └── docker-compose.yml       ← Jenkins LTS + Docker-in-Docker agent
├── scripts/
│   ├── migrate.py               ← create DB schema (idempotent)
│   ├── run_smoke_tests.sh       ← DAG trigger + status check
│   └── notify.sh                ← notification helper function
├── shared-library/              ← Jenkins shared library (reusable steps)
│   └── vars/
│       ├── terraformPlan.groovy
│       ├── terraformApply.groovy
│       └── airflowDagSync.groovy
├── requirements-dev.txt         ← pytest, ruff, mypy (for test stage in pipeline)
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
        stage('Approval')       { steps { input "${params.PIPELINE_ACTION.capitalize()} to ${params.ENVIRONMENT}?" } }
        stage('TF Apply')       { when { allOf {
                                      expression { params.PIPELINE_ACTION == 'deploy' }
                                      not { expression { params.DRY_RUN } }
                                  }}
                                  steps { sh 'terraform apply tfplan' } }
        stage('DB Migration')   { when { allOf {
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
        success  { echo 'Deployment succeeded' }
        failure  { echo 'Deployment failed — consider rollback' }
    }
}
```

## Local Jenkins Setup

```bash
# Start Jenkins via Docker Compose
cd backend/project2b-behavior-analyzer/docker
docker compose up -d

# Jenkins reachable via browser
open http://localhost:8080

# Retrieve initial admin password
docker exec jenkins-lts cat /var/jenkins_home/secrets/initialAdminPassword
```

## Secrets Configuration (Jenkins Credentials Store)

Add via Jenkins UI → Manage Jenkins → Credentials:

| ID | Type | Description |
|----|------|--------------|
| `aws-access-key-id` | Secret text | AWS Access Key ID |
| `aws-secret-access-key` | Secret text | AWS Secret Access Key |
| `db-password-dev` | Secret text | PostgreSQL password (dev) |
| `db-password-prod` | Secret text | PostgreSQL password (prod) |

**Never** commit AWS credentials in the `Jenkinsfile` or environment files.

## Environment Promotion Strategy

```
feature branch → dev      (automatic after CI green)
dev → staging             (manual approval via Jenkins input step)
staging → prod            (manual approval + second-pair sign-off)
```

## Installation & Usage

```bash
cd backend/project2b-behavior-analyzer

# 1. Start Jenkins
docker compose -f docker/docker-compose.yml up -d

# 2. Configure Jenkins (first time)
#    - Install plugins: Pipeline, Docker Pipeline, Credentials Binding
#    - Add credentials (AWS keys, DB passwords)
#    - Create pipeline job → link to this repository

# 3. Manually trigger pipeline
#    Jenkins UI → Pipeline → Build with Parameters

# 4. Debug pipeline locally (without Jenkins)
terraform plan -out=tfplan
terraform apply tfplan
python scripts/migrate.py
airflow dags sync
bash scripts/run_smoke_tests.sh
```

## Testing

```bash
# Test shared library Groovy steps (unit)
cd shared-library
./gradlew test

# Test scripts (bash)
bash -n scripts/run_smoke_tests.sh   # syntax check
bash -n scripts/notify.sh
```
