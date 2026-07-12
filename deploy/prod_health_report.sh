#!/bin/sh
set -e

echo "=== UNIQUE missing columns (all backend logs) ==="
docker logs deploy-backend-1 2>&1 | grep -oE 'no such column: [a-z0-9_.]+' | sort -u || true

echo ""
echo "=== UNIQUE missing tables ==="
docker logs deploy-backend-1 2>&1 | grep -oE 'no such table: [a-z0-9_]+' | sort -u || true

echo ""
echo "=== 500 endpoint counts ==="
docker logs deploy-backend-1 2>&1 | grep '500 Internal Server Error' | awk -F'"' '{print $2}' | sort | uniq -c | sort -rn | head -30

echo ""
echo "=== Recent errors (last 15 lines with ERROR) ==="
docker logs deploy-backend-1 2>&1 | grep ERROR | tail -15 || true

echo ""
echo "=== Startup / dependency issues ==="
docker logs deploy-backend-1 2>&1 | grep -iE 'ImportError|ModuleNotFoundError|libxcb|No space left|tenacity|Traceback' | grep -v 'starlette' | sort -u | tail -15 || true

echo ""
echo "=== API probe (no auth) ==="
for p in \
  /health \
  /api/ledgers \
  '/api/files?project_id=1' \
  '/api/entries?ledger_id=2&limit=1' \
  '/api/accounting-periods?ledger_id=2' \
  '/api/chart-of-accounts?ledger_id=2' \
  '/api/projects'
do
  code=$(curl -sk -o /tmp/body.txt -w '%{http_code}' "https://127.0.0.1${p}")
  snippet=$(head -c 80 /tmp/body.txt | tr '\n' ' ')
  echo "${code}  ${p}  |  ${snippet}"
done

echo ""
echo "=== Web container errors ==="
docker logs deploy-web-1 2>&1 | grep -iE 'error|502|503|504' | tail -10 || true

echo ""
echo "=== Backend image / code age ==="
docker exec deploy-backend-1 python -c "import app; print('app ok')" 2>&1
docker exec deploy-backend-1 sh -c 'ls -la /app/backend/app/main.py 2>/dev/null; head -1 /app/backend/pyproject.toml 2>/dev/null' || true
