#!/bin/sh
# One-time: migrate legacy production SQLite to formal Alembic tracking.
#
# Prerequisites:
#   - prod_schema_audit.py PASS (models align with DB)
#   - fix_legacy_db.py already applied all legacy columns
#
# What this does:
#   1. Backup /data/finance_audit.db
#   2. Re-run legacy patches + full schema audit (blocking)
#   3. alembic stamp head  (records current revision, does NOT re-run migrations)
#   4. alembic upgrade head (no-op if already at head)
#   5. Verify alembic_version + schema audit
#
# Usage (on server):
#   sh deploy/migrate_to_alembic.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BACKEND=deploy-backend-1
DB=/data/finance_audit.db
STAMP=$(date +%Y%m%d_%H%M%S)
BACKUP="/data/finance_audit.db.bak.${STAMP}"
HEAD_REV="0023_structured_import_staging"

for f in deploy/migrate_to_alembic.sh deploy/fix_legacy_db.py deploy/prod_schema_audit.py; do
  [ -f "$f" ] && sed -i 's/\r$//' "$f" 2>/dev/null || true
done

echo "=============================================="
echo " MIGRATE LEGACY DB → FORMAL ALEMBIC"
echo "=============================================="

echo ""
echo "=== [1/6] Check alembic_version not already present ==="
has_alembic=$(docker exec "$BACKEND" python -c "
import sqlite3
c = sqlite3.connect('$DB')
tables = {r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")}
print('yes' if 'alembic_version' in tables else 'no')
")
if [ "$has_alembic" = "yes" ]; then
  current=$(docker exec -w /app/backend "$BACKEND" alembic current 2>/dev/null | tail -1 || true)
  echo "alembic_version already exists. Current: $current"
  echo "Nothing to do. Use apply_prod_schema.sh for routine upgrades."
  exit 0
fi

echo ""
echo "=== [2/6] Backup database ==="
docker exec "$BACKEND" cp "$DB" "$BACKUP"
docker exec "$BACKEND" ls -lh "$BACKUP"
echo "Backup: $BACKUP"

echo ""
echo "=== [3/6] Legacy patches + schema audit (must PASS) ==="
docker cp deploy/fix_legacy_db.py "$BACKEND:/tmp/fix_legacy_db.py"
docker exec "$BACKEND" python /tmp/fix_legacy_db.py
docker cp deploy/prod_schema_audit.py "$BACKEND:/tmp/prod_schema_audit.py"
docker exec "$BACKEND" python /tmp/prod_schema_audit.py

echo ""
echo "=== [4/6] alembic stamp head ($HEAD_REV) ==="
docker exec -w /app/backend "$BACKEND" alembic stamp head
docker exec -w /app/backend "$BACKEND" alembic current

echo ""
echo "=== [5/6] alembic upgrade head (should be no-op) ==="
docker exec -w /app/backend "$BACKEND" alembic upgrade head
docker exec -w /app/backend "$BACKEND" alembic current

echo ""
echo "=== [6/6] Final schema audit ==="
docker exec "$BACKEND" python /tmp/prod_schema_audit.py

echo ""
echo "=============================================="
echo " MIGRATION SUCCESS"
echo " - alembic_version stamped at: $HEAD_REV"
echo " - backup: $BACKUP"
echo " - future deploys: apply_prod_schema.sh → alembic upgrade head"
echo "=============================================="
