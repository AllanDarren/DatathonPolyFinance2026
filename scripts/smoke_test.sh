#!/usr/bin/env bash
# Smoke test of the API. Usage: scripts/smoke_test.sh [BASE_URL]   (default: local server)
#   scripts/smoke_test.sh --deployed      # URL from .build/stack_outputs.json (after make deploy)
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-python3}"
if [[ "${1:-}" == "--deployed" ]]; then
  exec "$PY" scripts/smoke_test.py --deployed
fi
exec "$PY" scripts/smoke_test.py --base-url "${1:-http://127.0.0.1:8000}"
