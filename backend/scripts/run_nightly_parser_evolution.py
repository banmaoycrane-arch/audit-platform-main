# -*- coding: utf-8 -*-
"""CLI：Nightly TOP3 回归标尺（建议 cron 03:00，在提案扫描之前或之后均可）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import SessionLocal
from app.services.doc_parsing.parser_engine.parser_evolution_service import (
    run_nightly_top3_regression,
)


def main() -> None:
    db = SessionLocal()
    try:
        summary = run_nightly_top3_regression(db)
        print(f"Nightly regression {summary['run_id']}")
        cats = summary.get("categories") or {}
        if "journal" in cats:
            j = cats["journal"]
            print(f"  journal avg_quality={j.get('avg_quality')}% files={j.get('file_count')}")
        if "bank" in cats:
            b = cats["bank"]
            print(
                f"  bank files_with_rows={b.get('files_with_rows')}/"
                f"{b.get('file_count')} tx={b.get('total_transactions')}"
            )
        delta = summary.get("delta_vs_previous")
        if delta:
            print(f"  delta vs previous: {json.dumps(delta, ensure_ascii=False)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
