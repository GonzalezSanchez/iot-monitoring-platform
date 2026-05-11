#!/usr/bin/env bash
# Build Lambda deployment package for project 1a.
#
# Installs dependencies into dist/python/ (never into src/)
# and zips src/ + dist/python/ into dist/lambda_package.zip.
#
# Usage: ./scripts/build.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="${ROOT}/dist"

echo "[build] Installing dependencies to dist/python/ ..."
rm -rf "${DIST}"
mkdir -p "${DIST}/python"

pip install \
  -r "${ROOT}/requirements.txt" \
  --target "${DIST}/python" \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all: \
  --quiet

echo "[build] Packaging Lambda zip..."
cd "${DIST}"
cp -r "${ROOT}/src/." .
touch __init__.py
zip -r lambda_package.zip handlers/ utils/ repositories/ models/ services/ python/ __init__.py --quiet

echo "[build] Done: dist/lambda_package.zip"
