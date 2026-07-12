"""结构化导入文件格式预检测：编码、分隔符、表头预览。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.doc_parsing.charset_detection_service import delimiter_label
from app.services.doc_parsing.day_book_parser import resolve_structured_table
from app.services.doc_parsing.structured_parse_options import (
    StructuredParseOptions,
    parse_options_from_mapping,
    resolve_csv_delimiter,
    resolve_csv_encoding,
)


def detect_structured_file_format(
    file_path: str,
    parse_options: StructuredParseOptions | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """上传前/上传后均可调用，返回 charset、delimiter、表头预览等提示。"""
    if isinstance(parse_options, dict):
        options = parse_options_from_mapping(parse_options)
    else:
        options = parse_options or StructuredParseOptions()
    path = Path(file_path)
    suffix = path.suffix.lower()
    tabular = suffix in {".csv", ".tsv", ".xlsx", ".xls"}

    result: dict[str, Any] = {
        "file_name": path.name,
        "file_extension": suffix,
        "is_structured_tabular": tabular,
        "charset": None,
        "charset_confidence": None,
        "charset_source": None,
        "delimiter": None,
        "delimiter_label": None,
        "header_row_index": None,
        "detected_headers": [],
        "estimated_data_rows": 0,
        "company_name": None,
        "report_period": None,
        "parseable": False,
        "hints": [],
    }

    if suffix in {".csv", ".tsv"}:
        from app.services.doc_parsing.charset_detection_service import detect_text_encoding

        encoding = resolve_csv_encoding(path, options)
        delimiter = resolve_csv_delimiter(path, encoding=encoding, suffix=suffix, options=options)
        enc_info = detect_text_encoding(path) if not options.charset else {"source": "user"}
        result.update(
            {
                "charset": encoding,
                "charset_confidence": enc_info.get("confidence"),
                "charset_source": "user" if options.charset else enc_info.get("source"),
                "delimiter": delimiter,
                "delimiter_label": delimiter_label(delimiter),
            }
        )
        charset_note = "（手动指定）" if options.charset else ""
        delimiter_note = "（手动指定）" if options.delimiter else ""
        result["hints"].append(
            f"将使用编码 {encoding}{charset_note}，分隔符 {delimiter_label(delimiter)}{delimiter_note}"
        )
        if not options.charset and encoding.lower().startswith("gb"):
            result["hints"].append("文件疑似 GB 系列编码，已自动识别；若乱码请在下方改为 UTF-8 或 GB18030 后重试")
        if not options.delimiter:
            result["hints"].append("若列未对齐，可尝试切换分隔符：逗号 / Tab / 分号")
    elif suffix in {".xlsx", ".xls"}:
        result["hints"].append("Excel 二进制格式，无需指定字符集")
    else:
        result["hints"].append("非结构化表格格式，将走通用解析引擎")
        return result

    layout = resolve_structured_table(str(path), parse_options=options)
    if layout is None or layout.raw_frame.empty:
        result["hints"].append("未能识别有效表头，请确认包含凭证号/科目/借贷等列名")
        return result

    headers = [h for h in layout.raw_headers if h]
    result.update(
        {
            "header_row_index": layout.header_row_index,
            "detected_headers": headers[:30],
            "estimated_data_rows": len(layout.data_frame),
            "company_name": layout.metadata.company_name,
            "report_period": layout.metadata.report_period,
            "parseable": len(layout.data_frame) > 0,
        }
    )
    if headers:
        result["hints"].append(f"识别到表头（第 {layout.header_row_index + 1} 行），约 {len(layout.data_frame)} 行数据")
    return result
