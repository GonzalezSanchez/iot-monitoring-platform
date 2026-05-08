#!/usr/bin/env bash
# scripts/notify.sh
#
# Print a deployment summary to the Jenkins console.
# Extend with email/Slack integration as needed.

set -euo pipefail

ENVIRONMENT="${ENVIRONMENT:-unknown}"
PIPELINE_ACTION="${PIPELINE_ACTION:-unknown}"
BUILD_URL="${BUILD_URL:-n/a}"
BUILD_NUMBER="${BUILD_NUMBER:-n/a}"
BUILD_STATUS="${BUILD_STATUS:-unknown}"
GIT_COMMIT="${GIT_COMMIT:-n/a}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cat <<EOF
╔══════════════════════════════════════════════════════╗
║        Project 2b — Deployment Notification          ║
╚══════════════════════════════════════════════════════╝
  Status      : ${BUILD_STATUS}
  Action      : ${PIPELINE_ACTION}
  Environment : ${ENVIRONMENT}
  Build       : #${BUILD_NUMBER}
  Commit      : ${GIT_COMMIT}
  Timestamp   : ${TIMESTAMP}
  Build URL   : ${BUILD_URL}
═══════════════════════════════════════════════════════
EOF
