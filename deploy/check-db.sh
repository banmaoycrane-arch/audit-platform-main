#!/bin/sh
# 快速检查生产 SQLite 与 Alembic 状态（只读）
set -e
docker exec deploy-backend-1 python /tmp/fix_legacy_db.py 2>/dev/null && echo "(fix script present)" || true
docker cp deploy/fix_legacy_db.py deploy-backend-1:/tmp/fix_legacy_db.py 2>/dev/null || true
docker exec deploy-backend-1 python <<'PY'
import sqlite3
c = sqlite3.connect("/data/finance_audit.db")
cols = [r[1] for r in c.execute("PRAGMA table_info(ledgers)").fetchall()]
print("ledgers columns:", cols)
try:
    ver = c.execute("SELECT version_num FROM alembic_version").fetchone()
    print("alembic_version:", ver)
except sqlite3.OperationalError:
    print("alembic_version: MISSING (legacy DB)")
indexes = c.execute("PRAGMA index_list(chart_of_accounts)").fetchall()
print("chart_of_accounts indexes:", [(r[1], r[2]) for r in indexes])
PY
