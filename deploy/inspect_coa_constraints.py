"""Inspect and fix chart_of_accounts unique constraints for multi-ledger support."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(sys.argv[1] if len(sys.argv) > 1 else "/data/finance_audit.db")


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    print("=== indexes on chart_of_accounts ===")
    for row in conn.execute("PRAGMA index_list(chart_of_accounts)"):
        idx_name = row[1]
        unique = row[2]
        cols = [c[2] for c in conn.execute(f"PRAGMA index_info({idx_name})")]
        print(f"  {idx_name} unique={unique} cols={cols}")

    print("\n=== create table sql ===")
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='chart_of_accounts'"
    ).fetchone()
    print(row[0] if row else "missing")

    print("\n=== duplicate codes across ledgers ===")
    dups = conn.execute(
        """
        SELECT code, COUNT(DISTINCT COALESCE(ledger_id, -1)) AS ledger_cnt, COUNT(*) AS row_cnt
        FROM chart_of_accounts
        GROUP BY code
        HAVING row_cnt > 1
        LIMIT 10
        """
    ).fetchall()
    for d in dups:
        print(" ", d)

    conn.close()


if __name__ == "__main__":
    main()
