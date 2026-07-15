#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${TRACE_PROJECT_DIR:-/opt/trace}"
cd "${PROJECT_DIR}"

# The XXL-JOB shell executor must run on a host with Docker access.
export TRACE_ENV="${TRACE_ENV:-test}"
export TRACE_DB_CONFIG="${TRACE_DB_CONFIG:-./test-db.yml}"

exec docker compose run --rm --no-deps -T trace --summary-only --persist
