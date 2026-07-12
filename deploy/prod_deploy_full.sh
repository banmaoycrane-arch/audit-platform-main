#!/bin/sh
# Production deploy: code already on server → rebuild → schema → verify → web
#
# Prerequisites:
#   - Code synced to /root/audit-platform-main (see deploy/sync_and_deploy.ps1)
#   - deploy/.env present (not overwritten by sync)
#
# Usage:
#   ssh root@47.122.117.76 "sh /root/audit-platform-main/deploy/prod_deploy_full.sh"

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE="docker compose -f deploy/docker-compose.yml --env-file deploy/.env"
BACKEND=deploy-backend-1

for f in deploy/prod_deploy_full.sh deploy/apply_prod_schema.sh deploy/rebuild-slim-backend.sh; do
  [ -f "$f" ] && sed -i 's/\r$//' "$f" 2>/dev/null || true
done

echo "=============================================="
echo " PROD DEPLOY: code + data layer together"
echo "=============================================="

echo ""
echo "=== [1/5] Rebuild backend (no cache) ==="
$COMPOSE build --no-cache backend
$COMPOSE up -d backend

echo ""
echo "=== [2/5] Wait for backend health (max 60s) ==="
ready=0
i=0
while [ "$i" -lt 30 ]; do
  if docker exec "$BACKEND" python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()" >/dev/null 2>&1; then
    ready=1
    break
  fi
  i=$((i + 1))
  sleep 2
done
if [ "$ready" -ne 1 ]; then
  echo "ERROR: backend unhealthy"
  docker logs "$BACKEND" --tail 40
  exit 1
fi

echo ""
echo "=== [3/5] Apply DB schema + audit (BLOCKING) ==="
sh deploy/apply_prod_schema.sh

echo ""
echo "=== [4/5] Rebuild web ==="
# Alpine apk can hang without mirror; ensure Dockerfile uses Aliyun mirror
$COMPOSE build web
$COMPOSE up -d web

echo ""
echo "=== [5/5] Smoke checks ==="
curl -sk https://127.0.0.1/health
echo ""
for path in \
  "/api/files?project_id=1" \
  "/api/entries?ledger_id=2&limit=1" \
  "/api/accounting-periods?ledger_id=2"
do
  code=$(curl -sk -o /dev/null -w '%{http_code}' "https://127.0.0.1${path}")
  echo "  HTTP ${code}  ${path}"
  if [ "$code" = "500" ]; then
    echo "ERROR: smoke probe 500"
    exit 1
  fi
done

echo ""
echo "=============================================="
echo " DEPLOY SUCCESS"
echo " - Hard refresh browser (Ctrl+F5) after frontend changes"
echo " - Manual: login + one import flow if you changed auth/import"
echo "=============================================="
