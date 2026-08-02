#!/bin/sh
# -*- coding: utf-8 -*-
# 生产 Alembic 从 0028 升级到 0034（经济事件工单等）。
#
# Domain: 运维收口（配合 D14）
# In Scope: 备份 → fix_legacy → alembic upgrade head → schema 审计 → 校验经济事件表
# Out of Scope: 不改业务数据、不自动灌样例账、不替代 L6 人工签字
#
# Usage（在生产服务器仓库根目录）:
#   sh deploy/upgrade_prod_alembic_to_0034.sh
#
# 前置:
#   - 已拉取含 0029–0034 迁移的代码
#   - Docker 后端容器 deploy-backend-1 在跑
#   - 生产 stamp 预期为 0028_tax_city_egress_pool

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BACKEND=deploy-backend-1
DB_IN_CONTAINER=/data/finance_audit.db
TARGET_REV=0034_add_economic_event_workorder
EXPECTED_FROM=0028_tax_city_egress_pool
BACKUP_DIR="/data/backups"
STAMP="$(date +%Y%m%d_%H%M%S)"

for f in \
  deploy/upgrade_prod_alembic_to_0034.sh \
  deploy/fix_legacy_db.py \
  deploy/prod_schema_audit.py \
  deploy/apply_prod_schema.sh
do
  [ -f "$f" ] && sed -i 's/\r$//' "$f" 2>/dev/null || true
done

echo "=== [0/6] 检查后端容器 ==="
docker inspect "$BACKEND" >/dev/null 2>&1 || {
  echo "ERROR: 容器 $BACKEND 不存在，请先 docker compose up -d"
  exit 1
}

echo "=== [1/6] 读取当前 alembic_version ==="
CURRENT="$(docker exec -w /app/backend "$BACKEND" alembic current 2>/dev/null | tail -1 || true)"
echo "current: $CURRENT"
if echo "$CURRENT" | grep -q "$TARGET_REV"; then
  echo "已在 $TARGET_REV，跳过 upgrade（仍跑 schema 审计）。"
  SKIP_UPGRADE=1
else
  SKIP_UPGRADE=0
  if ! echo "$CURRENT" | grep -q "$EXPECTED_FROM"; then
    echo "WARN: 当前版本不是预期的 $EXPECTED_FROM"
    echo "      请人工确认 alembic current 后再继续。"
    printf "继续升级到 head？[y/N] "
    read -r ans
    case "$ans" in
      y|Y|yes|YES) ;;
      *) echo "已取消"; exit 2 ;;
    esac
  fi
fi

echo "=== [2/6] 备份生产 SQLite ==="
docker exec "$BACKEND" sh -c "mkdir -p $BACKUP_DIR && cp -a $DB_IN_CONTAINER $BACKUP_DIR/finance_audit_${STAMP}.db"
echo "backup: $BACKUP_DIR/finance_audit_${STAMP}.db"

echo "=== [3/6] Legacy 补列兜底（含 contracts.deep_analysis + 经济事件 4 表）==="
docker cp deploy/fix_legacy_db.py "$BACKEND:/tmp/fix_legacy_db.py"
docker exec "$BACKEND" python /tmp/fix_legacy_db.py

if [ "$SKIP_UPGRADE" = "0" ]; then
  echo "=== [4/6] alembic upgrade head（目标 $TARGET_REV）==="
  docker exec -w /app/backend "$BACKEND" alembic upgrade head
else
  echo "=== [4/6] 跳过 alembic upgrade ==="
fi
docker exec -w /app/backend "$BACKEND" alembic current

echo "=== [5/6] Schema 审计 ==="
docker cp deploy/prod_schema_audit.py "$BACKEND:/tmp/prod_schema_audit.py"
docker exec "$BACKEND" python /tmp/prod_schema_audit.py

echo "=== [6/6] 校验经济事件表存在 ==="
docker exec "$BACKEND" python -c "
import sqlite3
c = sqlite3.connect('$DB_IN_CONTAINER')
need = {
    'economic_events',
    'economic_event_entries',
    'economic_event_files',
    'economic_event_steps',
}
tables = {r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")}
missing = sorted(need - tables)
ver = c.execute('SELECT version_num FROM alembic_version').fetchone()
print('alembic_version:', ver[0] if ver else None)
if missing:
    raise SystemExit('MISSING tables: ' + ', '.join(missing))
print('OK economic event tables:', ', '.join(sorted(need)))
"

echo ""
echo "升级完成。"
echo "下一步建议："
echo "  1) 在 staging/生产跑 scripts/seed_demo_ledger.py 灌样例账（可选）"
echo "  2) 打开 /ledger/events 验证事件工单页"
echo "  3) L6 路径 A/B 人工签字仍需会计确认"
