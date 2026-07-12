#!/bin/sh
# 生产后端重建：精简镜像 + 自动 legacy schema 修复 + 校验
# 用法（在仓库根目录或任意目录）：
#   sh deploy/rebuild-slim-backend.sh
#
# 说明：
# - 重建不含 torch/easyocr 的 backend 镜像并重启
# - 重启后自动执行 deploy/fix_legacy_db.py（补列、COA 索引等）
# - 再跑 deploy/audit_model_schema.py 对照 SQLAlchemy 模型校验
# - 最后做 health / 关键 API 冒烟探测

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE="docker compose -f deploy/docker-compose.yml --env-file deploy/.env"
BACKEND=deploy-backend-1
WEB=deploy-web-1
DB_PATH=/data/finance_audit.db

# 避免 Windows 编辑导致 CRLF 在 Linux 上执行失败
for f in deploy/rebuild-slim-backend.sh deploy/fix_legacy_db.py deploy/audit_model_schema.py; do
  if [ -f "$f" ]; then
    sed -i 's/\r$//' "$f" 2>/dev/null || true
  fi
done

echo "=== Rebuild slim backend (no cache) ==="
$COMPOSE build --no-cache backend

echo "=== Restart backend ==="
$COMPOSE up -d backend

echo "=== Wait for backend health (max 60s) ==="
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
  echo "ERROR: backend did not become healthy within 60s"
  docker logs "$BACKEND" --tail 40 2>&1 || true
  exit 1
fi
echo "Backend is up."

echo "=== Verify packages (no torch/easyocr/nvidia) ==="
docker exec "$BACKEND" pip list | grep -iE 'torch|easyocr|nvidia|opencv' && {
  echo "WARN: unexpected heavy vision packages installed"
} || echo "OK: slim deps"

echo "=== Image size ==="
docker images deploy-backend --format '{{.Repository}}:{{.Tag}} {{.Size}}'

echo "=== Legacy schema fix (fix_legacy_db.py) ==="
if [ ! -f deploy/fix_legacy_db.py ]; then
  echo "ERROR: deploy/fix_legacy_db.py not found"
  exit 1
fi
docker cp deploy/fix_legacy_db.py "$BACKEND:/tmp/fix_legacy_db.py"
docker exec "$BACKEND" python /tmp/fix_legacy_db.py

echo "=== Schema audit (SQLAlchemy models vs SQLite) ==="
if [ ! -f deploy/audit_model_schema.py ]; then
  echo "WARN: deploy/audit_model_schema.py missing, skip audit"
else
  docker cp deploy/audit_model_schema.py "$BACKEND:/tmp/audit_model_schema.py"
  docker exec "$BACKEND" python /tmp/audit_model_schema.py
fi

echo "=== Public health (via web/Caddy) ==="
curl -sk https://127.0.0.1/health
echo

echo "=== Smoke APIs (unauthenticated) ==="
for path in \
  "/api/files?project_id=1" \
  "/api/entries?ledger_id=2&limit=1" \
  "/api/accounting-periods?ledger_id=2"
do
  code=$(curl -sk -o /dev/null -w '%{http_code}' "https://127.0.0.1${path}")
  echo "  HTTP ${code}  ${path}"
  if [ "$code" = "500" ]; then
    echo "ERROR: smoke probe returned 500 for ${path}"
    docker logs "$BACKEND" --tail 30 2>&1 || true
    exit 1
  fi
done

echo "=== Done ==="
echo "Tip: login-required routes (e.g. POST /api/ledgers) need manual UI check after deploy."
