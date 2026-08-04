#!/bin/sh
# 生产：重建 backend → Alembic upgrade head（含备份）→ 可选重建 web
# Usage (on server):
#   sh deploy/prod_upgrade_alembic_head.sh
#   SKIP_WEB=1 sh deploy/prod_upgrade_alembic_head.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE="docker compose -f deploy/docker-compose.yml --env-file deploy/.env"
BACKEND=deploy-backend-1
SKIP_WEB="${SKIP_WEB:-0}"

for f in deploy/prod_upgrade_alembic_head.sh deploy/upgrade_prod_alembic_to_head.sh deploy/apply_prod_schema.sh; do
  [ -f "$f" ] && sed -i 's/\r$//' "$f" 2>/dev/null || true
done
chmod +x deploy/upgrade_prod_alembic_to_head.sh 2>/dev/null || true

echo "=============================================="
echo " PROD: rebuild backend + Alembic → head"
echo "=============================================="

echo ""
echo "=== [1/4] Rebuild backend (no cache; migrations in image) ==="
$COMPOSE build --no-cache backend
$COMPOSE up -d backend

echo ""
echo "=== [2/4] Wait for backend health (max 60s) ==="
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
echo "=== [3/4] Alembic upgrade to head (backup + audit) ==="
AUTO_YES=1 sh deploy/upgrade_prod_alembic_to_head.sh

if [ "$SKIP_WEB" = "1" ]; then
  echo ""
  echo "=== [4/4] Skip web rebuild (SKIP_WEB=1) ==="
else
  echo ""
  echo "=== [4/4] Rebuild web ==="
  $COMPOSE build web
  $COMPOSE up -d web
fi

echo ""
echo "PROD Alembic head upgrade: OK"
echo "Verify: docker exec -w /app/backend $BACKEND alembic current"
