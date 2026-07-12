# -*- coding: utf-8 -*-
"""
TOP3 样本字段发现批跑（探索阶段）。

在 backend 目录运行:
    .\.venv\Scripts\python.exe scripts/top3_field_discovery.py

默认：规则引擎 + 格式识别（不调用 LLM，适合杂乱样本快速摸底）。
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[1]
TOP3_ROOT = BACKEND_ROOT / "samples" / "top3"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.doc_parsing.file_parser_service import parse_entries as parse_journal_entries
from app.services.doc_parsing.parser_engine.document_type_classifier import classify_document_type
from app.services.doc_parsing.parser_engine.format_recognizer import recognize_file_format
from app.services.doc_parsing.parser_engine.parse_result import DocumentType, ParseResult
from app.services.doc_parsing.parser_engine.parser_engine_dispatcher import (
    extract_text_from_file,
    parse_with_rule_engine,
)

CATEGORY_TYPE = {
    "journal": DocumentType.ACCOUNTING_ENTRY,
    "invoice": DocumentType.INVOICE,
    "bank": DocumentType.BANK_STATEMENT,
    "contract": DocumentType.CONTRACT,
}

JOURNAL_PREVIEW_FIELDS = [
    "voucher_date",
    "voucher_no",
    "summary",
    "account_name",
    "account_code",
    "debit_amount",
    "credit_amount",
    "counterparty",
]


def _json_default(obj: object) -> str:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    if hasattr(obj, "value"):
        return str(getattr(obj, "value"))
    return str(obj)


def _read_excel_meta(path: Path) -> dict:
    try:
        frame = pd.read_excel(path, header=None, nrows=6)
        return {
            "preview_rows": frame.fillna("").astype(str).values.tolist()[:4],
            "col_count": len(frame.columns),
        }
    except Exception as exc:
        return {"error": str(exc)}


def _read_csv_meta(path: Path) -> dict:
    try:
        frame = pd.read_csv(path, header=None, nrows=4, encoding_errors="ignore")
        return {"preview_rows": frame.fillna("").astype(str).values.tolist()[:4]}
    except Exception as exc:
        return {"error": str(exc)}


def _summarize_journal(path: Path) -> dict:
    result = parse_journal_entries(str(path))
    preview = []
    for entry in result.entries[:2]:
        preview.append({k: entry.get(k) for k in JOURNAL_PREVIEW_FIELDS})
    scenario = "A"
    notes: list[str] = []
    if result.quality_score < 50:
        notes.append("质量分偏低，表头/列映射可能未对齐")
    if result.unmatched_headers:
        notes.append(f"有 {len(result.unmatched_headers)} 个未映射表头")
    return {
        "scenario": scenario,
        "engine": "file_parser_service.parse_entries",
        "template_name": result.template_name,
        "matched_fields": result.matched_fields,
        "unmatched_headers": result.unmatched_headers,
        "total_rows": result.total_rows,
        "success_rows": result.success_rows,
        "error_rows": result.error_rows,
        "quality_score_pct": round(result.quality_score, 2),
        "entry_preview": preview,
        "excel_meta": _read_excel_meta(path) if path.suffix.lower() in {".xlsx", ".xls"} else None,
        "notes": notes,
    }


def _summarize_rule_parser(path: Path, preset_type: DocumentType) -> dict:
    fmt = recognize_file_format(str(path))
    if fmt.file_format.value == "unknown":
        return {
            "scenario": "?",
            "engine": "format_recognizer",
            "error": fmt.error_message or "无法识别文件格式",
        }

    type_result = classify_document_type(
        str(path),
        fmt.file_format,
        None,
        preset_type,
    )
    doc_type = type_result.document_type
    if doc_type == DocumentType.UNKNOWN:
        doc_type = preset_type

    text = ""
    text_error = None
    try:
        text = extract_text_from_file(str(path), fmt.file_format) or ""
    except Exception as exc:
        text_error = str(exc)

    rule_result: ParseResult = parse_with_rule_engine(
        str(path),
        doc_type,
        text,
        fmt.file_format,
        db=None,
    )

    scenario = "A"
    if fmt.file_format.value in {"pdf_image", "image"}:
        scenario = "B"
    elif fmt.file_format.value == "pdf_text" and len(text.strip()) < 80:
        scenario = "B"

    notes: list[str] = []
    if text_error:
        notes.append(f"文本提取异常: {text_error}")
    if scenario == "B" and rule_result.confidence < 0.3:
        notes.append("扫描/图片类，规则引擎置信度低，后续需 OCR/LLM/印章")
    if not rule_result.data:
        notes.append("规则引擎未提取到结构化字段")
    if type_result.document_type == DocumentType.UNKNOWN:
        notes.append(f"类型自动识别失败，已按目录假定 {preset_type.value}")

    data = rule_result.data or {}
    return {
        "scenario": scenario,
        "engine": "rule_engine (discovery, no LLM)",
        "detected_format": fmt.file_format.value,
        "detected_type": type_result.document_type.value,
        "used_type": doc_type.value,
        "type_confidence": round(type_result.confidence, 3),
        "confidence": round(rule_result.confidence, 3),
        "data_field_keys": list(data.keys()),
        "data_preview": {k: data[k] for k in list(data.keys())[:15]},
        "validation_errors": (rule_result.validation_errors or [])[:8],
        "text_len": len(text),
        "text_preview": text[:400].replace("\n", " ").strip(),
        "notes": notes,
    }


def _collect_files(category: str) -> list[Path]:
    folder = TOP3_ROOT / category
    if not folder.exists():
        return []
    return sorted(
        p
        for p in folder.iterdir()
        if p.is_file() and p.name.lower() not in {".gitkeep", "readme.md"}
        and not p.name.startswith("discovery_report")
    )


def _run_categories(categories: tuple[str, ...]) -> dict:
    report: dict = {
        "generated_at": datetime.now().isoformat(),
        "top3_root": str(TOP3_ROOT),
        "mode": "discovery_rule_only_no_llm",
        "categories": {},
        "summary": {},
    }

    for category in categories:
        files = _collect_files(category)
        items: list[dict] = []
        for path in files:
            item: dict = {
                "file": path.name,
                "size_kb": round(path.stat().st_size / 1024, 1),
                "suffix": path.suffix.lower(),
            }
            try:
                if category == "journal" and path.suffix.lower() in {".xlsx", ".xls", ".csv"}:
                    item.update(_summarize_journal(path))
                elif path.suffix.lower() in {".xlsx", ".xls"} and category in {"bank", "invoice"}:
                    item["excel_meta"] = _read_excel_meta(path)
                    item.update(_summarize_rule_parser(path, CATEGORY_TYPE[category]))
                elif path.suffix.lower() == ".csv":
                    item["csv_meta"] = _read_csv_meta(path)
                    item.update(_summarize_rule_parser(path, CATEGORY_TYPE[category]))
                else:
                    item.update(_summarize_rule_parser(path, CATEGORY_TYPE[category]))
            except Exception as exc:
                item["error"] = str(exc)
                item["trace"] = traceback.format_exc()[-500:]
            items.append(item)
            print(f"  [{category}] {path.name} -> {'OK' if not item.get('error') else 'ERR'}")

        ok = sum(1 for i in items if not i.get("error"))
        scenario_a = sum(1 for i in items if i.get("scenario") == "A")
        scenario_b = sum(1 for i in items if i.get("scenario") == "B")
        with_data = sum(1 for i in items if i.get("data_field_keys"))

        report["categories"][category] = {
            "file_count": len(items),
            "parsed_ok": ok,
            "parsed_failed": len(items) - ok,
            "scenario_a": scenario_a,
            "scenario_b": scenario_b,
            "with_structured_fields": with_data,
            "items": items,
        }

        cat_summary: dict = {"files": len(items), "ok": ok, "with_fields": with_data}
        if category == "journal" and items:
            qualities = [i.get("quality_score_pct", 0) for i in items if not i.get("error")]
            if qualities:
                cat_summary["avg_quality_score_pct"] = round(sum(qualities) / len(qualities), 2)
        report["summary"][category] = cat_summary

    return report


def _write_markdown(report: dict, out_md: Path) -> None:
    lines = [
        "# TOP3 字段发现报告（探索阶段 · 规则引擎摸底）",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        f"样本目录：`{report['top3_root']}`",
        "",
        f"模式：**{report['mode']}**（未调用 LLM；扫描/PDF 类后续需 OCR/语义层）",
        "",
        "## 总览",
        "",
    ]
    total = 0
    for cat, block in report["categories"].items():
        total += block["file_count"]
        lines.append(
            f"- **{cat}**：{block['file_count']} 份 | 成功 {block['parsed_ok']} | "
            f"场景A {block['scenario_a']} / 场景B {block['scenario_b']} | "
            f"有结构化字段 {block['with_structured_fields']}"
        )
        if report["summary"].get(cat, {}).get("avg_quality_score_pct") is not None:
            lines.append(f"  - 序时簿平均质量分：**{report['summary'][cat]['avg_quality_score_pct']}%**")
    lines.append(f"- **合计**：{total} 份")
    lines.extend(["", "---", ""])

    for cat, block in report["categories"].items():
        lines.append(f"## {cat.upper()}（{block['file_count']} 份）")
        lines.append("")
        for item in block["items"]:
            status = "❌" if item.get("error") else ("⚠️" if item.get("notes") else "✅")
            lines.append(f"### {status} {item['file']} ({item['size_kb']} KB, {item['suffix']})")
            lines.append("")
            if item.get("error"):
                lines.append(f"- **错误**：{item['error']}")
                lines.append("")
                continue

            if cat == "journal":
                lines.append(f"- 场景 **{item.get('scenario')}** | 模板 `{item.get('template_name')}` | 质量分 **{item.get('quality_score_pct')}%**")
                lines.append(f"- 行：总 {item.get('total_rows')} / 成 {item.get('success_rows')} / 败 {item.get('error_rows')}")
                lines.append(f"- 映射：{item.get('matched_fields')}")
                if item.get("unmatched_headers"):
                    lines.append(f"- 未识别表头：{item.get('unmatched_headers')}")
            else:
                lines.append(
                    f"- 场景 **{item.get('scenario')}** | 格式 `{item.get('detected_format')}` | "
                    f"类型 `{item.get('used_type')}` | 置信度 {item.get('confidence')}"
                )
                lines.append(f"- 提取字段：{item.get('data_field_keys') or '（无）'}")
                if item.get("data_preview"):
                    lines.append(
                        f"```json\n{json.dumps(item['data_preview'], ensure_ascii=False, indent=2, default=_json_default)}\n```"
                    )
                if item.get("text_preview"):
                    lines.append(f"- 文本片段：{item['text_preview'][:200]}…")

            if item.get("notes"):
                lines.append(f"- **待确认**：{'；'.join(item['notes'])}")
            lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--category",
        choices=["journal", "invoice", "bank", "contract", "all"],
        default="all",
        help="只跑指定类别（默认 all）",
    )
    args = parser.parse_args()
    categories = (
        ("journal", "invoice", "bank", "contract")
        if args.category == "all"
        else (args.category,)
    )

    print(f"Scanning {TOP3_ROOT} categories={categories} ...")
    report = _run_categories(categories)
    out_json = TOP3_ROOT / "discovery_report.json"
    out_md = TOP3_ROOT / "discovery_report.md"
    out_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    _write_markdown(report, out_md)
    print(f"\nWrote:\n  {out_json}\n  {out_md}")


if __name__ == "__main__":
    main()
