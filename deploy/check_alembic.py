import sqlite3

c = sqlite3.connect("/data/finance_audit.db")
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("ALL TABLES:", sorted(tables))
print("has_alembic_version:", "alembic_version" in tables)

if "alembic_version" in tables:
    rows = c.execute("SELECT * FROM alembic_version").fetchall()
    print("alembic_version rows:", rows)

print("---")
print("ledgers columns:", sorted(r[1] for r in c.execute("PRAGMA table_info(ledgers)").fetchall()))
print("has projects table:", "projects" in tables)
if "projects" in tables:
    print("projects columns:", sorted(r[1] for r in c.execute("PRAGMA table_info(projects)").fetchall()))
