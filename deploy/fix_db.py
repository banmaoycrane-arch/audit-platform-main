"""Legacy one-column fix — superseded by deploy/fix_legacy_db.py"""
import sqlite3c = sqlite3.connect("/data/finance_audit.db")
cols = [r[1] for r in c.execute("PRAGMA table_info(ledgers)").fetchall()]
print("ledgers columns:", cols)
if "organization_id" not in cols:
    print("Adding organization_id...")
    c.execute("ALTER TABLE ledgers ADD COLUMN organization_id INTEGER")
    c.commit()
    print("Fixed")
else:
    print("OK")
try:
    ver = c.execute("SELECT version_num FROM alembic_version").fetchone()
    print("alembic:", ver)
except sqlite3.OperationalError:
    print("alembic_version table missing (legacy DB)")
