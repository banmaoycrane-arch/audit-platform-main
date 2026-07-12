"""Fix chart_of_accounts: replace global code unique index with (ledger_id, code)."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(sys.argv[1] if len(sys.argv) > 1 else "/data/finance_audit.db")


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    print(f"DB: {DB_PATH}")
    rows = conn.execute("SELECT COUNT(*) AS c FROM chart_of_accounts").fetchone()["c"]
    print(f"rows: {rows}")
    for row in conn.execute(
        "SELECT ledger_id, COUNT(*) AS c FROM chart_of_accounts GROUP BY ledger_id ORDER BY ledger_id"
    ):
        print(f"  ledger_id={row['ledger_id']} count={row['c']}")

    dup = conn.execute(
        """
        SELECT ledger_id, code, COUNT(*) AS c
        FROM chart_of_accounts
        GROUP BY ledger_id, code
        HAVING c > 1
        """
    ).fetchall()
    if dup:
        print("ERROR: duplicate (ledger_id, code) pairs:", [dict(r) for r in dup])
        sys.exit(1)

    indexes = {
        row[1]: row[2]
        for row in conn.execute("PRAGMA index_list(chart_of_accounts)")
    }
    print("before indexes:", indexes)

    if "ix_chart_of_accounts_code" in indexes:
        print("DROP INDEX ix_chart_of_accounts_code")
        conn.execute("DROP INDEX ix_chart_of_accounts_code")

    existing = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='uq_chart_of_accounts_ledger_code'"
    ).fetchone()
    if not existing:
        print("CREATE UNIQUE INDEX uq_chart_of_accounts_ledger_code ON (ledger_id, code)")
        conn.execute(
            "CREATE UNIQUE INDEX uq_chart_of_accounts_ledger_code "
            "ON chart_of_accounts (ledger_id, code)"
        )
    else:
        print("OK uq_chart_of_accounts_ledger_code already exists")

    conn.commit()

    print("\nafter indexes:")
    for row in conn.execute("PRAGMA index_list(chart_of_accounts)"):
        idx_name = row[1]
        unique = row[2]
        cols = [c[2] for c in conn.execute(f"PRAGMA index_info({idx_name})")]
        print(f"  {idx_name} unique={unique} cols={cols}")
    print("Done")


if __name__ == "__main__":
    main()
