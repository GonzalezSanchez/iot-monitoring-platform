#!/usr/bin/env bash
# scripts/run_smoke_tests.sh
#
# Smoke test: trigger behavior_pipeline DAG with days_back=1 and wait for success.
# Used by the Jenkins CD pipeline after each deployment.
#
# Exit codes:
#   0  DAG run succeeded
#   1  DAG run failed or timed out

set -euo pipefail

AIRFLOW_URL="${AIRFLOW_URL:-http://localhost:8080}"
DAG_ID="behavior_pipeline"
TIMEOUT_SECONDS="${SMOKE_TEST_TIMEOUT:-300}"
POLL_INTERVAL=10

echo "[smoke] Triggering DAG '${DAG_ID}'..."
RUN_ID=$(
    airflow dags trigger "${DAG_ID}" \
        --conf '{"days_back": 1}' \
        --no-replace-microseconds \
        --output json \
    | python3 -c "import sys, json; print(json.load(sys.stdin)['run_id'])"
)
echo "[smoke] run_id: ${RUN_ID}"

echo "[smoke] Waiting for completion (timeout: ${TIMEOUT_SECONDS}s)..."
elapsed=0
while true; do
    STATE=$(
        airflow dags state "${DAG_ID}" "${RUN_ID}" \
        | tail -n 1
    )
    echo "[smoke] state=${STATE} (${elapsed}s elapsed)"

    case "${STATE}" in
        success)
            echo "[smoke] DAG succeeded."
            exit 0
            ;;
        failed|upstream_failed)
            echo "[smoke] DAG FAILED." >&2
            exit 1
            ;;
        running|queued)
            ;;
        *)
            echo "[smoke] Unexpected state: ${STATE}" >&2
            exit 1
            ;;
    esac

    if (( elapsed >= TIMEOUT_SECONDS )); then
        echo "[smoke] Timed out after ${TIMEOUT_SECONDS}s." >&2
        exit 1
    fi

    sleep "${POLL_INTERVAL}"
    elapsed=$(( elapsed + POLL_INTERVAL ))
done
