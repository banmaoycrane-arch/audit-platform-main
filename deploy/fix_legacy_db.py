"""One-shot legacy SQLite fixes for production deploy (no alembic_version).

Keep PATCHES in sync with backend/alembic/versions/ when adding model columns.
Run via deploy/apply_prod_schema.sh on every production deploy.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(sys.argv[1] if len(sys.argv) > 1 else "/data/finance_audit.db")

# table -> {column: ALTER TABLE ...}
PATCHES: dict[str, dict[str, str]] = {
    "ledgers": {
        "organization_id": "ALTER TABLE ledgers ADD COLUMN organization_id INTEGER",
        "accounting_start_date": "ALTER TABLE ledgers ADD COLUMN accounting_start_date DATE",
        "is_working": "ALTER TABLE ledgers ADD COLUMN is_working BOOLEAN DEFAULT 0 NOT NULL",
        "project_id": "ALTER TABLE ledgers ADD COLUMN project_id INTEGER",
    },
    "chart_of_accounts": {
        "ledger_id": "ALTER TABLE chart_of_accounts ADD COLUMN ledger_id INTEGER",
        "organization_id": "ALTER TABLE chart_of_accounts ADD COLUMN organization_id INTEGER",
        "account_category": "ALTER TABLE chart_of_accounts ADD COLUMN account_category VARCHAR(40)",
        "account_subcategory": "ALTER TABLE chart_of_accounts ADD COLUMN account_subcategory VARCHAR(40)",
        "equity_subcategory": "ALTER TABLE chart_of_accounts ADD COLUMN equity_subcategory VARCHAR(40)",
        "include_in_dividend_base": "ALTER TABLE chart_of_accounts ADD COLUMN include_in_dividend_base BOOLEAN",
    },
    "import_jobs": {
        "ledger_id": "ALTER TABLE import_jobs ADD COLUMN ledger_id INTEGER",
        "draft_data": "ALTER TABLE import_jobs ADD COLUMN draft_data JSON",
        "audit_scope_type": "ALTER TABLE import_jobs ADD COLUMN audit_scope_type VARCHAR(40)",
        "audit_period_id": "ALTER TABLE import_jobs ADD COLUMN audit_period_id INTEGER",
        "audit_account_codes": "ALTER TABLE import_jobs ADD COLUMN audit_account_codes JSON",
        "project_id": "ALTER TABLE import_jobs ADD COLUMN project_id INTEGER",
    },
    "accounting_periods": {
        "ledger_id": "ALTER TABLE accounting_periods ADD COLUMN ledger_id INTEGER",
        "period_type": "ALTER TABLE accounting_periods ADD COLUMN period_type VARCHAR(40) DEFAULT 'monthly' NOT NULL",
        "closed_at": "ALTER TABLE accounting_periods ADD COLUMN closed_at DATETIME",
        "reopened_at": "ALTER TABLE accounting_periods ADD COLUMN reopened_at DATETIME",
    },
    "source_files": {
        "ledger_id": "ALTER TABLE source_files ADD COLUMN ledger_id INTEGER",
        "text_extract_status": "ALTER TABLE source_files ADD COLUMN text_extract_status VARCHAR(40) DEFAULT 'pending' NOT NULL",
        "extracted_text": "ALTER TABLE source_files ADD COLUMN extracted_text TEXT",
        "counterparty_id": "ALTER TABLE source_files ADD COLUMN counterparty_id INTEGER",
        "customer_match_source": "ALTER TABLE source_files ADD COLUMN customer_match_source VARCHAR(80)",
        "customer_confidence_note": "ALTER TABLE source_files ADD COLUMN customer_confidence_note VARCHAR(300)",
        "notes": "ALTER TABLE source_files ADD COLUMN notes TEXT",
    },
    "accounting_entries": {
        "voucher_id": "ALTER TABLE accounting_entries ADD COLUMN voucher_id INTEGER",
    },
}


def table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in rows}


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def add_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    if column in columns(conn, table):
        print(f"  OK {table}.{column}")
        return
    print(f"  ADD {table}.{column}")
    conn.execute(ddl)


def default_ledger_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute("SELECT MIN(id) FROM ledgers").fetchone()
    return row[0] if row and row[0] is not None else None


def main() -> None:
    print(f"DB: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    existing_tables = table_names(conn)

    for table, patch in PATCHES.items():
        if table not in existing_tables:
            print(f"SKIP missing table: {table}")
            continue
        print(f"Patch {table}:")
        for column, ddl in patch.items():
            add_column(conn, table, column, ddl)

    ledger_id = default_ledger_id(conn)
    if ledger_id is not None and "chart_of_accounts" in existing_tables:
        if "ledger_id" in columns(conn, "chart_of_accounts"):
            updated = conn.execute(
                "UPDATE chart_of_accounts SET ledger_id = ? WHERE ledger_id IS NULL",
                (ledger_id,),
            ).rowcount
            if updated:
                print(f"  BACKFILL chart_of_accounts.ledger_id -> {ledger_id} ({updated} rows)")

    conn.commit()
    if "import_jobs" in existing_tables:
        print("import_jobs columns:", sorted(columns(conn, "import_jobs")))
    fix_chart_of_accounts_unique_index(conn)
    conn.commit()
    print("Done")


def fix_chart_of_accounts_unique_index(conn: sqlite3.Connection) -> None:
    if "chart_of_accounts" not in table_names(conn):
        return
    index_rows = conn.execute("PRAGMA index_list(chart_of_accounts)").fetchall()
    index_names = {row[1] for row in index_rows}
    if "ix_chart_of_accounts_code" in index_names:
        print("DROP INDEX ix_chart_of_accounts_code (legacy global code unique)")
        conn.execute("DROP INDEX ix_chart_of_accounts_code")
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='uq_chart_of_accounts_ledger_code'"
    ).fetchone()
    if not exists:
        print("CREATE UNIQUE INDEX uq_chart_of_accounts_ledger_code")
        conn.execute(
            "CREATE UNIQUE INDEX uq_chart_of_accounts_ledger_code "
            "ON chart_of_accounts (ledger_id, code)"
        )
    else:
        print("OK uq_chart_of_accounts_ledger_code")


if __name__ == "__main__":
    main()
