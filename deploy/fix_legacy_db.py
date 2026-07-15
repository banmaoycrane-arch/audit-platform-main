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
    "entry_tags": {
        "ledger_id": "ALTER TABLE entry_tags ADD COLUMN ledger_id INTEGER",
        "category_id": "ALTER TABLE entry_tags ADD COLUMN category_id INTEGER",
        "tag_type": "ALTER TABLE entry_tags ADD COLUMN tag_type VARCHAR(40)",
        "tag_value": "ALTER TABLE entry_tags ADD COLUMN tag_value VARCHAR(200)",
        "tag_value_normalized": "ALTER TABLE entry_tags ADD COLUMN tag_value_normalized VARCHAR(200)",
        "value_id": "ALTER TABLE entry_tags ADD COLUMN value_id INTEGER",
        "display_name": "ALTER TABLE entry_tags ADD COLUMN display_name VARCHAR(255)",
        "weight": "ALTER TABLE entry_tags ADD COLUMN weight REAL DEFAULT 1.0 NOT NULL",
        "vector_pending": "ALTER TABLE entry_tags ADD COLUMN vector_pending BOOLEAN DEFAULT 1 NOT NULL",
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

    if "entry_tags" in existing_tables and "accounting_entries" in existing_tables:
        if "ledger_id" in columns(conn, "entry_tags"):
            updated = conn.execute(
                """
                UPDATE entry_tags
                SET ledger_id = (
                    SELECT ae.ledger_id FROM accounting_entries ae
                    WHERE ae.id = entry_tags.entry_id
                )
                WHERE ledger_id IS NULL
                  AND EXISTS (
                    SELECT 1 FROM accounting_entries ae WHERE ae.id = entry_tags.entry_id
                  )
                """
            ).rowcount
            if updated:
                print(f"  BACKFILL entry_tags.ledger_id from accounting_entries ({updated} rows)")
            elif ledger_id is not None:
                updated = conn.execute(
                    "UPDATE entry_tags SET ledger_id = ? WHERE ledger_id IS NULL",
                    (ledger_id,),
                ).rowcount
                if updated:
                    print(f"  BACKFILL entry_tags.ledger_id -> {ledger_id} ({updated} rows)")

    conn.commit()
    if "import_jobs" in existing_tables:
        print("import_jobs columns:", sorted(columns(conn, "import_jobs")))
    if "entry_tags" in existing_tables:
        print("entry_tags columns:", sorted(columns(conn, "entry_tags")))
    fix_chart_of_accounts_unique_index(conn)
    ensure_product_events_table(conn)
    ensure_tax_egress_tables(conn)
    conn.commit()
    print("Done")


def ensure_product_events_table(conn: sqlite3.Connection) -> None:
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='product_events'"
    ).fetchone()
    if exists:
        print("OK product_events table")
        return
    print("CREATE TABLE product_events")
    conn.execute(
        """
        CREATE TABLE product_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name VARCHAR(80) NOT NULL,
            session_id VARCHAR(64),
            user_id INTEGER,
            team_id INTEGER,
            ledger_id INTEGER,
            job_id INTEGER,
            properties JSON,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX ix_product_events_event_name ON product_events (event_name)")
    conn.execute("CREATE INDEX ix_product_events_created_at ON product_events (created_at)")
    conn.execute("CREATE INDEX ix_product_events_session_id ON product_events (session_id)")
    conn.execute("CREATE INDEX ix_product_events_job_id ON product_events (job_id)")


def ensure_tax_egress_tables(conn: sqlite3.Connection) -> None:
    ddl_statements = [
        (
            "tax_city_egress_pools",
            """
            CREATE TABLE tax_city_egress_pools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                city_code VARCHAR(12) NOT NULL UNIQUE,
                city_name VARCHAR(80) NOT NULL,
                bureau_province VARCHAR(40) NOT NULL,
                pool_policy VARCHAR(40) DEFAULT 'sticky_with_failover' NOT NULL,
                max_rotate_per_taxpayer_7d INTEGER DEFAULT 2 NOT NULL,
                cooling_hours INTEGER DEFAULT 24 NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
            """,
        ),
        (
            "tax_egress_nodes",
            """
            CREATE TABLE tax_egress_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pool_id INTEGER NOT NULL,
                node_key VARCHAR(40) NOT NULL UNIQUE,
                egress_ip VARCHAR(64) NOT NULL,
                worker_host VARCHAR(200),
                provider VARCHAR(120),
                asn_type VARCHAR(40) DEFAULT 'enterprise' NOT NULL,
                status VARCHAR(20) DEFAULT 'active' NOT NULL,
                max_tenants INTEGER DEFAULT 5 NOT NULL,
                current_bindings INTEGER DEFAULT 0 NOT NULL,
                health_score REAL DEFAULT 1.0 NOT NULL,
                last_health_at DATETIME,
                cooling_until DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY(pool_id) REFERENCES tax_city_egress_pools(id)
            )
            """,
        ),
        (
            "tax_egress_bindings",
            """
            CREATE TABLE tax_egress_bindings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                taxpayer_id VARCHAR(32) NOT NULL UNIQUE,
                taxpayer_name VARCHAR(200) NOT NULL,
                ledger_id INTEGER,
                team_id INTEGER,
                city_code VARCHAR(12) NOT NULL,
                egress_node_id INTEGER NOT NULL,
                lease_start DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                lease_end DATETIME NOT NULL,
                rotate_count_7d INTEGER DEFAULT 0 NOT NULL,
                last_rotate_at DATETIME,
                session_state VARCHAR(20) DEFAULT 'idle' NOT NULL,
                binding_status VARCHAR(20) DEFAULT 'healthy' NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY(ledger_id) REFERENCES ledgers(id),
                FOREIGN KEY(egress_node_id) REFERENCES tax_egress_nodes(id)
            )
            """,
        ),
        (
            "tax_rotation_events",
            """
            CREATE TABLE tax_rotation_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                taxpayer_id VARCHAR(32) NOT NULL,
                binding_id INTEGER,
                old_node_id INTEGER,
                new_node_id INTEGER,
                old_egress_ip VARCHAR(64),
                new_egress_ip VARCHAR(64),
                trigger_code VARCHAR(40) NOT NULL,
                reason_detail TEXT,
                created_by VARCHAR(80) DEFAULT 'system' NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY(binding_id) REFERENCES tax_egress_bindings(id)
            )
            """,
        ),
    ]
    for table, ddl in ddl_statements:
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if exists:
            print(f"OK {table}")
            continue
        print(f"CREATE TABLE {table}")
        conn.execute(ddl)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_tax_egress_nodes_pool_id ON tax_egress_nodes (pool_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_tax_egress_bindings_ledger_id ON tax_egress_bindings (ledger_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_tax_rotation_events_created_at ON tax_rotation_events (created_at)"
    )


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
