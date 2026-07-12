#!/usr/bin/env python3
"""生产序时簿解析回归：标准样本 + 可选自定义文件路径。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.doc_parsing.file_parser_service import (
    build_parse_diagnostics,
    parse_structured_accounting_entries,
)


def run_sample(label: str, path: Path) -> dict:
    result = parse_structured_accounting_entries(str(path))
    diag = build_parse_diagnostics(result)
    return {
        "label": label,
        "path": str(path),
        "entries": len(result.entries),
        "success_rows": result.success_rows,
        "total_rows": result.total_rows,
        "engine": diag.get("engine"),
        "template": result.template_name,
        "unmatched_headers": result.unmatched_headers[:8],
        "ok": len(result.entries) > 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extra", action="append", default=[], help="额外待测 Excel/CSV 路径")
    args = parser.parse_args()

    samples: list[tuple[str, Path]] = [
        ("standard_test_daybook", BACKEND_DIR / "test_daybook.csv"),
    ]
    repo_root = BACKEND_DIR.parent
    optional = repo_root / "test_data.csv"
    if optional.exists():
        samples.append(("test_data", optional))
    for extra in args.extra:
        p = Path(extra)
        samples.append((p.name, p))

    reports = []
    required_ok = True
    for label, path in samples:
        if not path.exists():
            reports.append({"label": label, "path": str(path), "ok": False, "error": "file_not_found"})
            if label == "standard_test_daybook":
                required_ok = False
            continue
        try:
            report = run_sample(label, path)
            reports.append(report)
            if label == "standard_test_daybook" and not report["ok"]:
                required_ok = False
        except Exception as exc:
            reports.append({"label": label, "path": str(path), "ok": False, "error": str(exc)})
            if label == "standard_test_daybook":
                required_ok = False

    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0 if required_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
