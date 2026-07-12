#!/usr/bin/env bash
set -euo pipefail
ROOT="/root/audit-platform-main"
cd "$ROOT/deploy"

echo "=== Rebuild backend (no cache) ==="
docker compose build --no-cache backend
docker compose up -d backend
sleep 5

echo "=== Verify unified parser in container ==="
docker exec deploy-backend-1 grep -c parse_structured_accounting_entries /app/backend/app/services/doc_parsing/file_parser_service.py

echo "=== Parser unit regression (CSV samples) ==="
docker exec deploy-backend-1 python /app/backend/scripts/prod_regression_daybook.py

echo "=== API E2E regression ==="
docker exec deploy-backend-1 python /app/backend/scripts/prod_api_regression_daybook.py

echo "=== Rebuild web ==="
docker compose build web
docker compose up -d web

echo "=== Health ==="
curl -sf http://127.0.0.1:8000/health || curl -sk https://127.0.0.1/health || true
echo
echo "=== Done ==="
