#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${SERVER_URL:-http://127.0.0.1:8000}"

wait_for_health() {
  local i
  for i in $(seq 1 90); do
    if curl -sf "${BASE_URL}/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "Timed out waiting for ${BASE_URL}/health" >&2
  exit 1
}

wait_for_health
echo "--- POST /ingest"
curl -sf -X POST "${BASE_URL}/ingest" \
  | tee "${ROOT}/results/demo_ingest.json"
echo ""

echo "--- POST /evaluate"
curl -sf -X POST "${BASE_URL}/evaluate" \
  -H "Content-Type: application/json" \
  -d '{"case_file":"eval_cases/eval_cases.json"}' \
  | tee "${ROOT}/results/demo_evaluate.json"

echo ""
echo "Wrote:"
echo "  ${ROOT}/results/demo_ingest.json"
echo "  ${ROOT}/results/demo_evaluate.json"
