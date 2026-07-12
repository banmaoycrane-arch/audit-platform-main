# -*- coding: utf-8 -*-
"""CLI：运行 Parser Evolution Loop（可挂 cron / 云端定时任务）。"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import SessionLocal
from app.services.doc_parsing.parser_engine.parser_evolution_service import (
    list_proposals,
    proposal_to_dict,
    run_evolution_cycle,
)


def main() -> None:
    db = SessionLocal()
    try:
        summary = run_evolution_cycle(db)
        print(f"Evolution run {summary['run_id']}: {summary['new_proposals']} new proposals")
        if summary.get("proposal_ids"):
            drafts = list_proposals(db, status="draft", limit=20)
            for p in drafts[:10]:
                d = proposal_to_dict(p)
                print(f"  - [{d['id']}] {d['source_header']} -> {d['target_field']} ({d['evidence_file']})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
