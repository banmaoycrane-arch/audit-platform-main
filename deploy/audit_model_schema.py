"""Compare all SQLAlchemy model columns vs production SQLite (read-only)."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from sqlalchemy import inspect as sa_inspect

from app.db.session import engine
from app.db import models  # noqa: F401 - register all models

DB_PATH = Path(sys.argv[1] if len(sys.argv) > 1 else "/data/finance_audit.db")


def sqlite_tables(conn: sqlite3.Connection) -> dict[str, set[str]]:
    names = [
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        if not r[0].startswith("sqlite_")
    ]
    return {t: {c[1] for c in conn.execute(f"PRAGMA table_info({t})")} for t in names}


def main() -> None:
    print(f"SQLite file: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    db = sqlite_tables(conn)
    conn.close()

    inspector = sa_inspect(engine)
    model_tables = sorted(inspector.get_table_names())

    missing_tables: list[str] = []
    missing_columns: list[str] = []
    extra_info: list[str] = []

    for table in model_tables:
        if table not in db:
            missing_tables.append(table)
            continue
        model_cols = {c["name"] for c in inspector.get_columns(table)}
        db_cols = db[table]
        for col in sorted(model_cols - db_cols):
            missing_columns.append(f"{table}.{col}")
        orphan = db_cols - model_cols
        if orphan:
            extra_info.append(f"{table}: DB-only columns {sorted(orphan)}")

    print("\n=== Model tables missing in DB ===")
    if missing_tables:
        for t in missing_tables:
            print(f"  {t}")
    else:
        print("  (none)")

    print(f"\n=== Model columns missing in DB ({len(missing_columns)}) ===")
    for item in missing_columns[:80]:
        print(f"  {item}")
    if len(missing_columns) > 80:
        print(f"  ... and {len(missing_columns) - 80} more")

    if extra_info:
        print("\n=== DB-only columns (informational) ===")
        for line in extra_info[:20]:
            print(f"  {line}")

    if missing_tables or missing_columns:
        sys.exit(1)
    print("\nSchema check: OK")


if __name__ == "__main__":
    main()
