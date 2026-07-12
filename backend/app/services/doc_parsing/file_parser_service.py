"""
会计凭证文件解析服务

支持多种格式的自适应字段映射
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

from app.money import parse_decimal
from app.services.doc_parsing.day_book_parser import (
    is_summary_row,
    load_accounting_frame,
)
from app.services.doc_parsing.format_template import (
    STANDARD_FIELDS,
    detect_template,
    get_required_fields,
    is_valid_template,
    match_header,
)


@dataclass
class ParseResult:
    """解析结果"""
    entries: list[dict[str, Any]]
    template_name: str | None
    matched_fields: dict[str, str]
    unmatched_headers: list[str]
    total_rows: int
    success_rows: int
    error_rows: int
    quality_score: float = 0.0


@dataclass
class RowParseResult:
    """单行解析结果"""
    data: dict[str, Any]
    success: bool
    error_message: str | None = None
    missing_fields: list[str] = field(default_factory=list)


def _normalize_key(key: str) -> str:
    """标准化键名"""
    return str(key).strip().lower()


def _amount(value: Any) -> Decimal:
    """
    功能描述：解析金额为 Decimal
    业务逻辑：清理货币符号和千分位后，转换为 Decimal 并保留 2 位小数
    会计口径：统一使用 Decimal，避免 float 精度误差
    """
    if value is None or pd.isna(value):
        return Decimal("0.00")
    try:
        cleaned = str(value).replace(",", "").replace("¥", "").replace("$", "").strip()
        return parse_decimal(cleaned, decimal_places=2, allow_empty=True)
    except Exception:
        return Decimal("0.00")


def _date(value: Any) -> date | None:
    """解析日期"""
    if value is None or pd.isna(value):
        return None
    try:
        if isinstance(value, (datetime, date)):
            return value.date() if isinstance(value, datetime) else value
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        parsed_date: date = parsed.date()
        return parsed_date
    except Exception:
        return None


def _normalize_text(value: Any) -> str:
    """标准化文本"""
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _parse_amount_with_sign(value: Any, debit_default: bool = True) -> tuple[Decimal, Decimal]:
    """
    功能描述：解析带符号的金额并拆分为借方/贷方
    业务逻辑：正数为借方，负数为贷方；debit_default 控制默认方向
    会计口径：返回 Decimal 元组，确保后续金额计算精度
    """
    amount = _amount(value)
    zero = Decimal("0.00")
    if amount == zero:
        return zero, zero
    if amount > zero:
        return (amount, zero) if debit_default else (zero, amount)
    else:
        return (zero, abs(amount)) if debit_default else (abs(amount), zero)


def _has_amount_field(headers: list[str]) -> tuple[bool, bool]:
    """检测是否有借方/贷方字段"""
    debit_keywords = ["借方", "借", "debit", "dr"]
    credit_keywords = ["贷方", "贷", "credit", "cr"]

    has_debit = any(any(kw in h.lower() for kw in debit_keywords) for h in headers)
    has_credit = any(any(kw in h.lower() for kw in credit_keywords) for h in headers)

    return has_debit, has_credit


def _infer_amount_direction(row: dict[str, Any], has_debit: bool, has_credit: bool) -> tuple[Decimal, Decimal]:
    """
    功能描述：推断借贷方向
    业务逻辑：优先使用明确借贷字段；单个金额字段时根据方向推断
    会计口径：返回 Decimal 元组，避免 float 精度误差
    """
    zero = Decimal("0.00")
    debit_amount = _amount(row.get("debit_amount") or row.get("debit") or 0)
    credit_amount = _amount(row.get("credit_amount") or row.get("credit") or 0)

    # 如果有明确的借贷字段
    if has_debit or has_credit:
        return debit_amount, credit_amount

    # 从单个金额字段推断
    amount = debit_amount + credit_amount
    if amount == zero:
        return zero, zero

    # 检查是否有借或贷标记
    for key, value in row.items():
        if pd.isna(value) or _amount(value) == zero:
            continue
        key_lower = key.lower()
        if "借" in key_lower or "dr" in key_lower:
            return _amount(value), zero
        if "贷" in key_lower or "cr" in key_lower:
            return zero, _amount(value)

    return amount, zero  # 默认借方


def _build_mapping(frame: pd.DataFrame, extra_aliases: dict[str, str] | None = None) -> tuple[dict[str, str], list[str]]:
    """
    构建字段映射

    Returns:
        (header_to_field, unmatched_headers)
    """
    headers = [str(h) for h in frame.columns]
    template_name, detected_mapping = detect_template(headers)

    # 构建完整映射
    mapping: dict[str, str] = {}
    unmatched: list[str] = []

    for header in headers:
        normalized = _normalize_key(header)
        matched = None
        if extra_aliases and normalized in extra_aliases:
            matched = extra_aliases[normalized]
        if not matched:
            matched = match_header(header)

        if matched:
            mapping[normalized] = matched
        else:
            unmatched.append(header)

    return mapping, unmatched


def _map_row(row: pd.Series, mapping: dict[str, str]) -> dict[str, Any]:
    """映射单行数据"""
    result: dict[str, Any] = {}

    for header, value in row.items():
        normalized = _normalize_key(header)
        if normalized in mapping:
            field_name = mapping[normalized]
            result[field_name] = value

    return result


def _split_account(value: Any) -> tuple[str, str]:
    text = _normalize_text(value)
    if not text:
        return "", ""
    parts = text.split(maxsplit=1)
    if len(parts) == 2 and parts[0].replace(".", "").isdigit():
        return parts[0], parts[1]
    return "", text


def _transform_row(row: dict[str, Any], has_debit: bool, has_credit: bool) -> dict[str, Any]:
    """转换行数据"""
    # 处理金额
    debit_amount, credit_amount = _infer_amount_direction(row, has_debit, has_credit)

    # 处理日期
    voucher_date = _date(row.get("voucher_date"))
    account_code = _normalize_text(row.get("account_code", ""))
    account_name = _normalize_text(row.get("account_name", ""))
    if account_name and not account_code:
        split_code, split_name = _split_account(account_name)
        account_code = split_code
        account_name = split_name

    summary = _normalize_text(row.get("summary", ""))
    counterparty = _normalize_text(row.get("counterparty", ""))
    source_preparer_name = _normalize_text(
        row.get("source_preparer_name", "") or row.get("source_preparer", "")
    )

    # 解析科目层级并生成建议 Tag
    from app.config.account_tag_config import load_account_tag_config
    from app.services.doc_parsing.account_tag_resolution_service import (
        resolve_account_for_import,
    )
    from app.services.doc_parsing.parse_context import get_parse_db, get_parse_ledger_id

    parse_db = get_parse_db()
    parse_ledger_id = get_parse_ledger_id()
    tag_config = load_account_tag_config(parse_db, ledger_id=parse_ledger_id)
    resolved = resolve_account_for_import(
        account_code,
        account_name,
        summary,
        config=tag_config,
    )

    # 构建 normalized_text
    parts = [
        summary,
        account_name,
        account_code,
        resolved.account_name,
    ]
    zero = Decimal("0.00")
    if debit_amount > zero:
        parts.append(f"借{debit_amount}")
    if credit_amount > zero:
        parts.append(f"贷{credit_amount}")
    parts.append(counterparty)
    for tag in resolved.suggested_tags:
        parts.append(f"{tag.get('category_code', '')}:{tag.get('tag_value', '')}")

    normalized_text = " ".join(p for p in parts if p)

    entry_line_no = None
    raw_line_no = row.get("entry_line_no")
    if raw_line_no is not None and not (isinstance(raw_line_no, float) and pd.isna(raw_line_no)):
        try:
            entry_line_no = int(str(raw_line_no).strip().split(".", 1)[0])
        except (TypeError, ValueError):
            entry_line_no = None

    return {
        "voucher_no": _normalize_text(row.get("voucher_no")),
        "voucher_type": _normalize_text(row.get("voucher_type")),
        "voucher_date": voucher_date,
        "summary": summary,
        "account_code": account_code,
        "account_name": account_name,
        "resolved_account_code": resolved.account_code,
        "resolved_account_name": resolved.account_name,
        "suggested_tags": resolved.suggested_tags,
        "resolved_counterparty": resolved.counterparty_name or counterparty,
        "requires_llm_resolution": resolved.requires_llm_resolution,
        "debit_amount": debit_amount,
        "credit_amount": credit_amount,
        "counterparty": counterparty,
        "entry_line_no": entry_line_no,
        "source_preparer_name": source_preparer_name or None,
        "original_row": dict(row),
        "normalized_text": normalized_text,
    }


def _validate_row(row: dict[str, Any], required_fields: list[str]) -> tuple[bool, list[str]]:
    """验证行数据"""
    missing = []
    for field_name in required_fields:
        value = row.get(field_name)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field_name)
    return len(missing) == 0, missing


def _empty_parse_result() -> ParseResult:
    return ParseResult(
        entries=[],
        template_name=None,
        matched_fields={},
        unmatched_headers=[],
        total_rows=0,
        success_rows=0,
        error_rows=0,
        quality_score=0.0,
    )


def _parse_frame_to_result(
    frame: pd.DataFrame,
    *,
    db: Any = None,
    extra_aliases: dict[str, str] | None = None,
    engine_label: str = "adaptive_template",
    data_row_excel_indices: list[int] | None = None,
    amount_color_grid: dict[tuple[int, int], str] | None = None,
) -> ParseResult:
    headers = list(frame.columns)
    aliases: dict[str, str] = dict(extra_aliases or {})
    if db is not None:
        from app.services.doc_parsing.parser_engine.parser_evolution_service import (
            get_active_column_header_aliases,
        )

        aliases.update(get_active_column_header_aliases(db, "accounting_entry"))

    mapping, unmatched = _build_mapping(frame, extra_aliases=aliases or None)
    template_name, _ = detect_template(headers)
    has_debit, has_credit = _has_amount_field(headers)
    required_fields = get_required_fields(template_name or "") if template_name else ["summary", "account_name"]

    entries: list[dict[str, Any]] = []
    success_rows = 0
    error_rows = 0
    row_signals: list[dict[str, bool]] = []
    last_voucher_type = ""
    last_voucher_serial = ""
    last_composed_voucher = ""
    last_voucher_date: date | None = None

    from app.services.doc_parsing.voucher_no_resolution import (
        _cell_has_value,
        assign_parse_group_keys,
        resolve_voucher_no_from_parts,
    )
    from app.services.doc_parsing.excel_font_amount_service import infer_debit_credit_from_colored_row

    for frame_idx, (_, row) in enumerate(frame.iterrows()):
        try:
            if is_summary_row(row):
                continue
            mapped = _map_row(row, mapping)
            row_signals.append(
                {
                    "raw_had_date": _cell_has_value(mapped.get("voucher_date")),
                    "raw_had_voucher_no": _cell_has_value(mapped.get("voucher_no")),
                }
            )
            if _cell_has_value(mapped.get("voucher_date")):
                parsed_boundary_date = _date(mapped.get("voucher_date"))
                if parsed_boundary_date and last_voucher_date and parsed_boundary_date != last_voucher_date:
                    last_voucher_type = ""
                    last_voucher_serial = ""
                    last_composed_voucher = ""
            composed, last_voucher_type, last_voucher_serial, last_composed_voucher = (
                resolve_voucher_no_from_parts(
                    raw_voucher_no=mapped.get("voucher_no"),
                    raw_voucher_type=mapped.get("voucher_type"),
                    last_type=last_voucher_type,
                    last_serial=last_voucher_serial,
                    last_composed=last_composed_voucher,
                )
            )
            mapped["voucher_no"] = composed
            transformed = _transform_row(mapped, has_debit, has_credit)
            if amount_color_grid is not None and data_row_excel_indices and frame_idx < len(data_row_excel_indices):
                row_values = [row.iloc[col] if col < len(row) else None for col in range(len(headers))]
                colored_debit, colored_credit, _used_color = infer_debit_credit_from_colored_row(
                    row_values=row_values,
                    headers=headers,
                    excel_row_index=data_row_excel_indices[frame_idx],
                    color_grid=amount_color_grid,
                    has_debit_column=has_debit,
                    has_credit_column=has_credit,
                )
                transformed["debit_amount"] = colored_debit
                transformed["credit_amount"] = colored_credit
            if transformed.get("voucher_date"):
                last_voucher_date = transformed["voucher_date"]
            elif last_voucher_date:
                transformed["voucher_date"] = last_voucher_date

            is_valid, _missing = _validate_row(transformed, required_fields)
            zero = Decimal("0.00")
            has_amount = transformed["debit_amount"] != zero or transformed["credit_amount"] != zero
            if is_valid and has_amount:
                entries.append(transformed)
                success_rows += 1
            else:
                error_rows += 1
                row_signals.pop()
        except Exception:
            error_rows += 1

    assign_parse_group_keys(entries, row_signals)

    total_rows = len(frame)
    quality_score = (success_rows / max(total_rows, 1)) * 100
    matched_fields = {v: k for k, v in mapping.items()}
    matched_fields["engine"] = engine_label
    return ParseResult(
        entries=entries,
        template_name=template_name,
        matched_fields=matched_fields,
        unmatched_headers=unmatched,
        total_rows=total_rows,
        success_rows=success_rows,
        error_rows=error_rows,
        quality_score=quality_score,
    )


def _parse_entries_via_rule_engine(path: str, db: Any = None) -> ParseResult:
    """规则引擎回退：与 parser_engine.accounting_entry 同一套表头/汇总行逻辑。"""
    from app.services.doc_parsing.parser_engine.rule_parsers import parse_accounting_entry_rules

    rule_data = parse_accounting_entry_rules("", file_path=path)
    raw_entries = rule_data.get("entries") or []
    if not raw_entries:
        return _empty_parse_result()

    entries: list[dict[str, Any]] = []
    success_rows = 0
    row_signals: list[dict[str, bool]] = []
    last_voucher_type = ""
    last_voucher_serial = ""
    last_composed_voucher = ""
    last_voucher_date: date | None = None

    from app.services.doc_parsing.voucher_no_resolution import (
        _cell_has_value,
        assign_parse_group_keys,
        resolve_voucher_no_from_parts,
    )

    for raw in raw_entries:
        row_signals.append(
            {
                "raw_had_date": _cell_has_value(raw.get("date")),
                "raw_had_voucher_no": _cell_has_value(raw.get("document_no")),
            }
        )
        if _cell_has_value(raw.get("date")):
            parsed_boundary_date = _date(raw.get("date"))
            if parsed_boundary_date and last_voucher_date and parsed_boundary_date != last_voucher_date:
                last_voucher_type = ""
                last_voucher_serial = ""
                last_composed_voucher = ""
        composed, last_voucher_type, last_voucher_serial, last_composed_voucher = (
            resolve_voucher_no_from_parts(
                raw_voucher_no=raw.get("document_no"),
                raw_voucher_type=raw.get("voucher_type"),
                last_type=last_voucher_type,
                last_serial=last_voucher_serial,
                last_composed=last_composed_voucher,
            )
        )
        mapped = {
            "voucher_no": composed,
            "voucher_date": raw.get("date"),
            "summary": _normalize_text(raw.get("summary")),
            "account_code": _normalize_text(raw.get("subject_code")),
            "account_name": _normalize_text(raw.get("subject_name")),
            "debit_amount": raw.get("debit_amount") or 0,
            "credit_amount": raw.get("credit_amount") or 0,
            "counterparty": _normalize_text(raw.get("counterparty_subject")),
        }
        transformed = _transform_row(mapped, True, True)
        if transformed.get("voucher_date"):
            last_voucher_date = transformed["voucher_date"]
        elif last_voucher_date:
            transformed["voucher_date"] = last_voucher_date
        zero = Decimal("0.00")
        if transformed["debit_amount"] != zero or transformed["credit_amount"] != zero:
            entries.append(transformed)
            success_rows += 1
        else:
            row_signals.pop()

    assign_parse_group_keys(entries, row_signals)

    columns = rule_data.get("columns") or []
    return ParseResult(
        entries=entries,
        template_name="rule_engine_accounting_entry",
        matched_fields={"engine": "rule_engine", "columns": ", ".join(columns[:12])},
        unmatched_headers=[c for c in columns if c],
        total_rows=len(raw_entries),
        success_rows=success_rows,
        error_rows=max(len(raw_entries) - success_rows, 0),
        quality_score=(success_rows / max(len(raw_entries), 1)) * 100,
    )


def parse_structured_accounting_entries(
    path: str,
    db: Any = None,
    parse_options: StructuredParseOptions | None = None,
) -> ParseResult:
    """
    场景 A 统一结构化分录解析入口（序时簿/凭证 Excel/CSV）。

    与 document-parsing-engine / adaptive-import-engine 设计一致：
    1. 自适应模板 + evolution column_header 规则
    2. 失败时回退 parser_engine 序时簿规则解析（同一数据模型输出）
    """
    from app.services.doc_parsing.structured_parse_options import get_parse_options
    from app.services.doc_parsing.day_book_parser import resolve_structured_table

    options = parse_options or get_parse_options()
    layout = resolve_structured_table(path, parse_options=options)
    if layout is None or layout.data_frame.empty:
        return _empty_parse_result()

    primary = _parse_frame_to_result(
        layout.data_frame,
        db=db,
        engine_label="adaptive_template",
        data_row_excel_indices=layout.data_row_excel_indices,
        amount_color_grid=layout.amount_color_grid,
    )
    if primary.entries:
        return primary

    fallback = _parse_entries_via_rule_engine(path, db=db)
    if fallback.entries:
        return fallback

    return primary if primary.total_rows >= fallback.total_rows else fallback


def parse_entries(path: str, db: Any = None) -> ParseResult:
    """
    解析会计分录文件（兼容旧调用方，内部走统一入口）。
    """
    return parse_structured_accounting_entries(path, db=db)


def extract_text(path: str) -> str:
    """提取文本内容（用于原始文件）"""
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix in {".txt", ".csv"}:
        return file_path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".pdf":
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)

    # 图片 OCR 支持
    if suffix in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}:
        from app.services.doc_parsing.ocr_service import extract_text_from_image

        return extract_text_from_image(path)

    return ""


def build_parse_diagnostics(parse_result: ParseResult) -> dict[str, Any]:
    """生成列映射诊断信息，供前端展示分列引导。"""
    engine = parse_result.matched_fields.get("engine", "adaptive_template")
    return {
        "template_name": parse_result.template_name,
        "matched_fields": parse_result.matched_fields,
        "unmatched_headers": parse_result.unmatched_headers,
        "total_rows": parse_result.total_rows,
        "success_rows": parse_result.success_rows,
        "error_rows": parse_result.error_rows,
        "quality_score": round(parse_result.quality_score, 2),
        "engine": engine,
        "expected_columns": list(STANDARD_FIELDS.values()),
        "guidance": (
            "请检查表头是否包含：凭证号、凭证日期、摘要、科目名称、借方金额、贷方金额等列。"
            "系统已使用统一结构化解析引擎（自适应模板 + 规则引擎回退）。"
            f"当前引擎分支：{engine}。"
        ),
    }
