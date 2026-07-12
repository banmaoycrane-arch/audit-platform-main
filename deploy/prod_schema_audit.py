"""Full production schema audit: models vs SQLite, Alembic drift, risk summary."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from sqlalchemy import inspect as sa_inspect

from app.db.session import engine
from app.db import models  # noqa: F401

DB_PATH = Path(sys.argv[1] if len(sys.argv) > 1 else "/data/finance_audit.db")

# Tables that must exist for recent features (existence check only)
FEATURE_TABLES = (
    "staging_accounting_entries",
    "staging_account_balances",
    "staging_general_ledger_lines",
    "staging_general_ledger_summary",
    "parse_quality_metric",
    "parse_quality_summary",
    "vouchers",
)


def sqlite_snapshot(conn: sqlite3.Connection) -> dict[str, set[str]]:
    tables = [
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        if not r[0].startswith("sqlite_")
    ]
    return {t: {c[1] for c in conn.execute(f"PRAGMA table_info({t})")} for t in tables}


def alembic_info(conn: sqlite3.Connection) -> str:
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "alembic_version" not in names:
        return "MISSING (legacy DB — migrations never stamped)"
    row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    return row[0] if row else "EMPTY"


def main() -> int:
    print(f"SQLite: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    db = sqlite_snapshot(conn)
    alembic = alembic_info(conn)
    conn.close()

    print(f"alembic_version: {alembic}")
    print(f"DB tables: {len(db)}")

    inspector = sa_inspect(engine)
    model_tables = sorted(inspector.get_table_names())

    missing_tables: list[str] = []
    missing_columns: list[str] = []
    db_only: list[str] = []

    for table in model_tables:
        if table not in db:
            missing_tables.append(table)
            continue
        model_cols = {c["name"] for c in inspector.get_columns(table)}
        db_cols = db[table]
        for col in sorted(model_cols - db_cols):
            missing_columns.append(f"{table}.{col}")
        orphan = sorted(db_cols - model_cols)
        if orphan:
            db_only.append(f"{table}: {orphan}")

    missing_feature_tables = [t for t in FEATURE_TABLES if t not in db]

    print("\n=== 1. Model tables missing in DB ===")
    print("  (none)" if not missing_tables else "\n".join(f"  {t}" for t in missing_tables))

    print(f"\n=== 2. Model columns missing in DB ({len(missing_columns)}) ===")
    if missing_columns:
        for item in missing_columns:
            print(f"  {item}")
    else:
        print("  (none)")

    print(f"\n=== 3. Feature tables checklist ({len(missing_feature_tables)} missing) ===")
    if missing_feature_tables:
        for t in missing_feature_tables:
            print(f"  MISSING TABLE: {t}")
    else:
        for t in FEATURE_TABLES:
            print(f"  OK {t} ({len(db[t])} cols)")

    print("\n=== 4. DB-only columns (informational, first 15) ===")
    if db_only:
        for line in db_only[:15]:
            print(f"  {line}")
        if len(db_only) > 15:
            print(f"  ... and {len(db_only) - 15} more")
    else:
        print("  (none)")

    ok = not (missing_tables or missing_columns or missing_feature_tables)
    print("\n=== RESULT ===")
    if ok:
        print("PASS — code models align with production SQLite schema")
        if alembic.startswith("MISSING"):
            print("WARN — alembic_version not stamped; use fix_legacy_db.py on each deploy until migrated to Alembic")
        return 0
    print("FAIL — schema drift detected; run deploy/apply_prod_schema.sh before serving traffic")
    return 1


if __name__ == "__main__":
    sys.exit(main())
