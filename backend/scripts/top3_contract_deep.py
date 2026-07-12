# -*- coding: utf-8 -*-
"""对指定合同样本做深度解析（规则 + 文本 + ContractDeepAnalyzer）。"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = BACKEND_ROOT / "samples" / "top3" / "contract"
sys.path.insert(0, str(BACKEND_ROOT))

TARGET_KEYWORDS = ["吕梁国益测绘有限公司_0001", "岚县民立仓储运销有限公司_可搜索"]


def _json_default(obj: object) -> str:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    if hasattr(obj, "value"):
        return str(getattr(obj, "value"))
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return str(obj)


def _find_targets() -> list[Path]:
    files = []
    for path in CONTRACT_DIR.iterdir():
        if not path.is_file():
            continue
        for kw in TARGET_KEYWORDS:
            if kw in path.name:
                files.append(path)
                break
    return sorted(files)


def _deep_parse(path: Path) -> dict:
    from app.services.doc_parsing.parser_engine.document_type_classifier import classify_document_type
    from app.services.doc_parsing.parser_engine.format_recognizer import recognize_file_format
    from app.services.doc_parsing.parser_engine.parse_result import DocumentType
    from app.services.doc_parsing.parser_engine.parser_engine_dispatcher import (
        extract_text_from_file,
        parse_with_rule_engine,
    )
    from app.services.doc_parsing.parser_engine.contract_deep_analyzer import ContractDeepAnalyzer

    fmt = recognize_file_format(str(path))
    type_result = classify_document_type(
        str(path), fmt.file_format, None, DocumentType.CONTRACT
    )
    text = extract_text_from_file(str(path), fmt.file_format) or ""
    rule = parse_with_rule_engine(
        str(path),
        DocumentType.CONTRACT,
        text,
        fmt.file_format,
        db=None,
    )

    analyzer = ContractDeepAnalyzer()
    deep = analyzer.analyze(text, rule.data or {})

    data_preview = {k: (rule.data or {}).get(k) for k in list((rule.data or {}).keys())[:20]}

    return {
        "file": path.name,
        "format": fmt.file_format.value,
        "text_len": len(text),
        "text_preview": text[:800],
        "rule_confidence": rule.confidence,
        "parsed_fields": data_preview,
        "deep_analysis": deep.to_dict(),
    }


def main() -> None:
    targets = _find_targets()
    if not targets:
        print("未找到目标合同文件，关键词:", TARGET_KEYWORDS)
        sys.exit(1)

    results = []
    for path in targets:
        print(f"Deep parsing: {path.name}")
        results.append(_deep_parse(path))

    out_json = CONTRACT_DIR / "contract_deep_report.json"
    out_md = CONTRACT_DIR / "contract_deep_report.md"
    out_json.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")

    lines = ["# 合同样本深解析报告", ""]
    for item in results:
        lines.append(f"## {item['file']}")
        lines.append(f"- 格式：`{item['format']}` | 文本长度 {item['text_len']} | 规则置信度 {item['rule_confidence']}")
        lines.append(f"- 解析字段：```json\n{json.dumps(item['parsed_fields'], ensure_ascii=False, indent=2)}\n```")
        da = item["deep_analysis"]
        lines.append(f"- 风险等级：**{da.get('overall_risk_level')}** | 风险分 {da.get('risk_score')}")
        lines.append(f"- 摘要：{da.get('analysis_summary')}")
        lines.append(f"- 缺失要素 {len(da.get('missing_elements', []))} 项 | 非标条款 {len(da.get('non_standard_clauses', []))} 项")
        if da.get("missing_elements"):
            lines.append("- 缺失：" + "、".join(m["element_name"] for m in da["missing_elements"][:8]))
        lines.append("")
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")


if __name__ == "__main__":
    main()
