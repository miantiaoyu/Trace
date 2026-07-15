#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${TRACE_PROJECT_DIR:-/opt/trace}"
cd "${PROJECT_DIR}"

# The XXL-JOB shell executor must run on a host with Docker access.
export TRACE_ENV="${TRACE_ENV:-test}"
export TRACE_DB_CONFIG="${TRACE_DB_CONFIG:-./test-db.yml}"

if docker compose version >/dev/null 2>&1; then
  compose=(docker compose)
else
  compose=(docker-compose)
fi

exec "${compose[@]}" run --rm --no-deps -T trace \
  --db-config /run/secrets/trace-db.yml \
  --days 7 \
  --limit "${TRACE_LIMIT:-0}" \
  --lock-file /var/lib/trace/.trace-api-probe.lock \
  --run-log /var/lib/trace/trace-runs.jsonl \
  --health-state /var/lib/trace/trace-health.json \
  --alert-threshold 3 \
  --summary-only \
  --persist
