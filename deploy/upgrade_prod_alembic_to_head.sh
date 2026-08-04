#!/bin/sh
# -*- coding: utf-8 -*-
# 生产 Alembic：从当前版本（预期 0028）升级到代码 tip head（含 0034 经济事件 + 0035 DocumentTag.ledger_id）。
#
# Domain: 运维收口（TD-020）
# In Scope: 备份 → fix_legacy → alembic upgrade head → schema 审计 → 关键表/列校验
# Out of Scope: 不改业务数据、不自动灌样例账、不替代 L6 人工签字
#
# Usage（在生产服务器仓库根目录）:
#   sh deploy/upgrade_prod_alembic_to_head.sh
# 非交互（脚本/CI）:
#   AUTO_YES=1 sh deploy/upgrade_prod_alembic_to_head.sh
#
# 前置:
#   - 已同步含 0029–0035 迁移的代码，且已重建 backend 镜像（迁移文件在容器内）
#   - Docker 后端容器 deploy-backend-1 在跑
#   - 生产 stamp 预期为 0028_tax_city_egress_pool（其他版本需确认后 AUTO_YES=1）

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BACKEND=deploy-backend-1
DB_IN_CONTAINER=/data/finance_audit.db
EXPECTED_FROM=0028_tax_city_egress_pool
TARGET_HINT=0035_document_tag_ledger_id
BACKUP_DIR="/data/backups"
STAMP="$(date +%Y%m%d_%H%M%S)"
AUTO_YES="${AUTO_YES:-0}"

for f in \
  deploy/upgrade_prod_alembic_to_head.sh \
  deploy/fix_legacy_db.py \
  deploy/prod_schema_audit.py \
  deploy/apply_prod_schema.sh
do
  [ -f "$f" ] && sed -i 's/\r$//' "$f" 2>/dev/null || true
done

echo "=== [0/7] 检查后端容器 ==="
docker inspect "$BACKEND" >/dev/null 2>&1 || {
  echo "ERROR: 容器 $BACKEND 不存在，请先 docker compose up -d"
  exit 1
}

echo "=== [1/7] 读取当前 alembic_version ==="
CURRENT="$(docker exec -w /app/backend "$BACKEND" alembic current 2>/dev/null | tail -1 || true)"
echo "current: $CURRENT"
if echo "$CURRENT" | grep -q "$TARGET_HINT"; then
  echo "已在 head 附近（含 $TARGET_HINT），仍跑 schema 审计与表校验。"
  SKIP_UPGRADE=1
else
  SKIP_UPGRADE=0
  if ! echo "$CURRENT" | grep -q "$EXPECTED_FROM"; then
    echo "WARN: 当前版本不是预期的 $EXPECTED_FROM"
    echo "      请人工确认 alembic current 后再继续。"
    if [ "$AUTO_YES" != "1" ]; then
      printf "继续升级到 head？[y/N] "
      read -r ans
      case "$ans" in
        y|Y|yes|YES) ;;
        *) echo "已取消"; exit 2 ;;
      esac
    else
      echo "AUTO_YES=1：继续升级到 head"
    fi
  fi
fi

echo "=== [2/7] 备份生产 SQLite ==="
docker exec "$BACKEND" sh -c "mkdir -p $BACKUP_DIR && cp -a $DB_IN_CONTAINER $BACKUP_DIR/finance_audit_${STAMP}.db"
echo "backup: $BACKUP_DIR/finance_audit_${STAMP}.db"

echo "=== [3/7] Legacy 补列兜底（deep_analysis / 经济事件 / document_tags.ledger_id）==="
docker cp deploy/fix_legacy_db.py "$BACKEND:/tmp/fix_legacy_db.py"
docker exec "$BACKEND" python /tmp/fix_legacy_db.py

if [ "$SKIP_UPGRADE" = "0" ]; then
  echo "=== [4/7] alembic upgrade head（目标含 $TARGET_HINT）==="
  docker exec -w /app/backend "$BACKEND" alembic upgrade head
else
  echo "=== [4/7] 跳过 alembic upgrade ==="
fi
docker exec -w /app/backend "$BACKEND" alembic current

echo "=== [5/7] Schema 审计 ==="
docker cp deploy/prod_schema_audit.py "$BACKEND:/tmp/prod_schema_audit.py"
docker exec "$BACKEND" python /tmp/prod_schema_audit.py

echo "=== [6/7] 校验经济事件表存在 ==="
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

echo "=== [7/7] 校验 document_tags.ledger_id ==="
docker exec "$BACKEND" python -c "
import sqlite3
c = sqlite3.connect('$DB_IN_CONTAINER')
cols = {r[1] for r in c.execute('PRAGMA table_info(document_tags)')}
if 'ledger_id' not in cols:
    raise SystemExit('MISSING column: document_tags.ledger_id')
print('OK document_tags.ledger_id')
ver = c.execute('SELECT version_num FROM alembic_version').fetchone()
print('alembic_version:', ver[0] if ver else None)
"

echo ""
echo "升级完成。"
echo "下一步建议："
echo "  1) 打开 https://47.122.117.76:8443/login 硬刷新"
echo "  2) （可选）staging 跑 scripts/seed_demo_ledger.py"
echo "  3) L6 路径 A/B 人工签字仍需会计确认"
