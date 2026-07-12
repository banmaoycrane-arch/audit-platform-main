"""Audit production SQLite schema against SQLAlchemy models (read-only)."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(sys.argv[1] if len(sys.argv) > 1 else "/data/finance_audit.db")

# Minimal required columns inferred from recent production failures + models
REQUIRED: dict[str, list[str]] = {
    "ledgers": ["organization_id", "accounting_start_date", "is_working", "project_id"],
    "chart_of_accounts": ["ledger_id", "organization_id", "account_category"],
    "import_jobs": [
        "ledger_id",
        "draft_data",
        "audit_scope_type",
        "audit_period_id",
        "audit_account_codes",
        "project_id",
    ],
    "accounting_entries": ["ledger_id", "voucher_id", "post_status", "review_status"],
    "accounting_periods": ["ledger_id", "period_type"],
    "source_files": ["ledger_id", "text_extract_status"],
    "users": ["platform_role", "last_ledger_id"],
    "vouchers": [],  # table may be missing entirely
}


def table_names(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def main() -> None:
    print(f"DB: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    tables = table_names(conn)

    try:
        ver = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        print(f"alembic_version: {ver[0] if ver else None}")
    except sqlite3.OperationalError:
        print("alembic_version: MISSING (legacy DB, migrations never stamped)")

    missing_tables: list[str] = []
    missing_columns: list[str] = []

    for table, cols in REQUIRED.items():
        if table not in tables:
            if cols or table == "vouchers":
                missing_tables.append(table)
            continue
        present = columns(conn, table)
        for col in cols:
            if col not in present:
                missing_columns.append(f"{table}.{col}")

    print("\n--- Missing tables ---")
    if missing_tables:
        for t in missing_tables:
            print(f"  MISSING TABLE: {t}")
    else:
        print("  (none in checklist)")

    print("\n--- Missing columns ---")
    if missing_columns:
        for item in missing_columns:
            print(f"  MISSING COLUMN: {item}")
    else:
        print("  (none in checklist)")

    print("\n--- All tables ---")
    for t in sorted(tables):
        if t.startswith("sqlite_"):
            continue
        print(f"  {t} ({len(columns(conn, t))} cols)")

    conn.close()
    if missing_tables or missing_columns:
        sys.exit(1)


if __name__ == "__main__":
    main()
