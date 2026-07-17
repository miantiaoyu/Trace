#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${TRACE_PROJECT_DIR:-/opt/trace}"
cd "${PROJECT_DIR}"

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --source-config|--target-config)
      if [[ "$#" -lt 2 ]]; then
        echo "$1 缺少配置文件路径。" >&2
        exit 2
      fi
      if [[ "$1" == "--source-config" ]]; then
        TRACE_SOURCE_CONFIG="$2"
      else
        TRACE_TARGET_CONFIG="$2"
      fi
      shift 2
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

export TRACE_SOURCE_CONFIG="${TRACE_SOURCE_CONFIG:-./prod-db.yml}"
export TRACE_TARGET_CONFIG="${TRACE_TARGET_CONFIG:-./test-db.yml}"

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
  --persist \
  "$@"
