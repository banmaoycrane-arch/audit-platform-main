#!/bin/sh
# Apply production DB schema patches and verify against SQLAlchemy models.
# Safe to run while backend is up (SQLite ADD COLUMN).
#
# Usage (on server, from repo root):
#   sh deploy/apply_prod_schema.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BACKEND=deploy-backend-1
COMPOSE="docker compose -f deploy/docker-compose.yml --env-file deploy/.env"

for f in deploy/apply_prod_schema.sh deploy/fix_legacy_db.py deploy/prod_schema_audit.py; do
  [ -f "$f" ] && sed -i 's/\r$//' "$f" 2>/dev/null || true
done

echo "=== Step 1: Legacy column patches (fix_legacy_db.py) ==="
docker cp deploy/fix_legacy_db.py "$BACKEND:/tmp/fix_legacy_db.py"
docker exec "$BACKEND" python /tmp/fix_legacy_db.py

echo "=== Step 2: Alembic upgrade head ==="
if docker exec "$BACKEND" python -c "
import sqlite3
c = sqlite3.connect('/data/finance_audit.db')
tables = {r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")}
print('yes' if 'alembic_version' in tables else 'no')
" | grep -q yes; then
  docker exec -w /app/backend "$BACKEND" alembic upgrade head
  docker exec -w /app/backend "$BACKEND" alembic current
else
  echo "WARN — legacy DB (no alembic_version)."
  echo "      Run once: sh deploy/migrate_to_alembic.sh"
  echo "      Falling back to fix_legacy_db.py only for this deploy."
fi

echo "=== Step 3: Full schema audit (models vs SQLite) ==="
docker cp deploy/prod_schema_audit.py "$BACKEND:/tmp/prod_schema_audit.py"
docker exec "$BACKEND" python /tmp/prod_schema_audit.py

echo "=== Schema apply: OK ==="
