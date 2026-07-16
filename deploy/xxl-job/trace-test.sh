#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${TRACE_PROJECT_DIR:-/opt/trace}"
cd "${PROJECT_DIR}"

if docker compose version >/dev/null 2>&1; then
  compose=(docker compose)
else
  compose=(docker-compose)
fi

exec "${compose[@]}" run --rm --no-deps -T trace \
  --days "${TRACE_DAYS:-60}" \
  --limit "${TRACE_LIMIT:-0}" \
  --lock-file /var/lib/trace/.trace-api-probe.lock \
  --run-log /var/lib/trace/trace-runs.jsonl \
  --detail-log /var/lib/trace/trace-detail.jsonl \
  --health-state /var/lib/trace/trace-health.json \
  --alert-threshold 3 \
  --summary-only \
  --persist
