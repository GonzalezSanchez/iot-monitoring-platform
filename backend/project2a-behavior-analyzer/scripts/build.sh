#!/usr/bin/env bash
# Build Lambda deployment packages for project 2a.
#
# Creates in dist/:
#   staging/{extract,transform,analyze}/   <- staged source files
#   dependencies-layer.zip                 <- psycopg2-binary + python-dotenv layer
#
# Terraform's archive_file data sources pick up the staged directories
# and produce the final Lambda zips.
#
# Usage: ./scripts/build.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="${ROOT}/dist"

echo "[build] Staging Lambda source files..."

for FUNC in extract transform analyze; do
  STAGING="${DIST}/staging/${FUNC}"
  rm -rf "${STAGING}"
  mkdir -p "${STAGING}"

  cp "${ROOT}/lambdas/${FUNC}/handler.py" "${STAGING}/"

  # __init__.py (may not exist in all lambdas)
  [[ -f "${ROOT}/lambdas/${FUNC}/__init__.py" ]] && \
    cp "${ROOT}/lambdas/${FUNC}/__init__.py" "${STAGING}/"

  # Shared module
  cp -r "${ROOT}/lambdas/shared" "${STAGING}/"

  echo "  staged: ${FUNC}"
done

echo ""
echo "[build] Building dependency layer (psycopg2-binary, python-dotenv)..."
echo "        Target platform: manylinux2014_x86_64 (Amazon Linux 2 compatible)"

LAYER_DIR="${DIST}/layer/python"
rm -rf "${DIST}/layer"
mkdir -p "${LAYER_DIR}"

pip install \
  psycopg2-binary \
  python-dotenv \
  --target "${LAYER_DIR}" \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.11 \
  --only-binary=:all: \
  --quiet

(cd "${DIST}/layer" && zip -r "${DIST}/dependencies-layer.zip" python/ --quiet)
echo "  built: dependencies-layer.zip"

echo ""
echo "Build complete. Artifacts:"
echo "  ${DIST}/staging/          <- Lambda source (Terraform archive_file)"
echo "  ${DIST}/dependencies-layer.zip  <- Lambda layer"
