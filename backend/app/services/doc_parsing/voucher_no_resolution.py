"""序时簿/日记账凭证号识别：凭证字+凭证号组合、续行继承、格式归一。"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

from app.services.doc_parsing.format_template import match_header

# 单独一列「凭证字」时不能当作完整凭证号
_VOUCHER_TYPE_WORDS = frozenset({"记", "收", "付", "转", "银", "现", "工", "转字", "记字"})

_VOUCHER_NO_HEADER_ALIASES = frozenset(
    {
        "凭证号",
        "凭证编号",
        "单据号",
        "单据编号",
        "记字号",
        "凭证字号",
        "编号",
        "字号",
        "凭证序号",
        "voucher_no",
        "voucher_number",
        "doc_no",
    }
)

_VOUCHER_TYPE_HEADER_ALIASES = frozenset(
    {
        "凭证字",
        "凭证字号",
        "voucher_type",
        "voucher_word",
    }
)

_DATE_HEADER_HINTS = ("日期", "时间", "date", "voucher_date")


def normalize_voucher_serial(value: Any) -> str:
    """归一化凭证序号（Excel 数值 1.0 → 1，保留前导零字符串）。"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return ""
    if re.fullmatch(r"\d+", text):
        return text
    if re.fullmatch(r"\d+\.0+", text):
        return text.split(".", 1)[0]
    try:
        dec = Decimal(text.replace(",", ""))
        if dec == dec.to_integral_value():
            return format(dec.to_integral_value(), "f").split(".")[0]
    except (InvalidOperation, ValueError):
        pass
    return text


def looks_like_full_voucher_no(value: str) -> bool:
    """是否已是完整凭证号（如 记-0001、银-12）。"""
    text = (value or "").strip()
    if not text:
        return False
    if text in _VOUCHER_TYPE_WORDS:
        return False
    if re.fullmatch(r"\d+", text):
        return False
    if "-" in text:
        return True
    if re.search(r"[A-Za-z\u4e00-\u9fff]", text) and re.search(r"\d", text):
        return True
    return False


def split_voucher_no(voucher_no: str) -> tuple[str, str]:
    if "-" in voucher_no:
        voucher_type, serial = voucher_no.split("-", 1)
        return voucher_type.strip(), serial.strip()
    return "", voucher_no.strip()


def compose_voucher_no(voucher_type: str, voucher_serial: str) -> str:
    vtype = (voucher_type or "").strip()
    serial = normalize_voucher_serial(voucher_serial)
    if not serial and not vtype:
        return ""
    if serial and looks_like_full_voucher_no(serial):
        return serial
    if vtype and serial:
        if serial.startswith(f"{vtype}-"):
            return serial
        return f"{vtype}-{serial}"
    if serial:
        return serial
    return ""


def resolve_voucher_no_from_parts(
    *,
    raw_voucher_no: Any,
    raw_voucher_type: Any,
    last_type: str,
    last_serial: str,
    last_composed: str,
) -> tuple[str, str, str, str]:
    """
    从当前行原始单元格 + 上一行状态解析凭证号。

    Returns:
        (composed_voucher_no, next_last_type, next_last_serial, next_last_composed)
    """
    cell_type = str(raw_voucher_type or "").strip()
    cell_no = str(raw_voucher_no or "").strip()

    if cell_no and looks_like_full_voucher_no(cell_no):
        composed = cell_no
        vtype, serial = split_voucher_no(composed)
        return composed, vtype or last_type, serial or last_serial, composed

    next_type = cell_type or last_type
    serial_from_cell = normalize_voucher_serial(cell_no)
    if serial_from_cell and not looks_like_full_voucher_no(serial_from_cell):
        next_serial = serial_from_cell
    elif serial_from_cell:
        composed = serial_from_cell
        vtype, serial = split_voucher_no(composed)
        return composed, vtype or next_type, serial or last_serial, composed
    else:
        next_serial = last_serial

    composed = compose_voucher_no(next_type, next_serial)
    if composed:
        return composed, next_type, next_serial, composed
    if last_composed:
        return last_composed, next_type, next_serial, last_composed
    return "", next_type, next_serial, last_composed


def _cell_has_value(value: Any) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return bool(str(value).strip()) and str(value).strip().lower() not in {"nan", "none", "null"}


def _parse_date_cell(value: Any) -> date | None:
    if not _cell_has_value(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.date()
    except Exception:
        return None


def resolve_voucher_column_indices(headers: list[str]) -> tuple[int | None, int | None, int | None]:
    """根据表头别名定位凭证号/凭证字/日期列（与 format_template 一致）。"""
    voucher_no_idx: int | None = None
    voucher_type_idx: int | None = None
    voucher_date_idx: int | None = None

    for idx, header in enumerate(headers):
        header_text = str(header).strip()
        normalized = header_text.lower()
        field = match_header(header_text)

        if field == "voucher_no" and voucher_no_idx is None:
            voucher_no_idx = idx
        elif field == "voucher_type" and voucher_type_idx is None:
            voucher_type_idx = idx
        elif field == "voucher_date" and voucher_date_idx is None:
            voucher_date_idx = idx

        if header_text in _VOUCHER_NO_HEADER_ALIASES or normalized in {a.lower() for a in _VOUCHER_NO_HEADER_ALIASES}:
            voucher_no_idx = idx if voucher_no_idx is None else voucher_no_idx
        if header_text in _VOUCHER_TYPE_HEADER_ALIASES or normalized in {a.lower() for a in _VOUCHER_TYPE_HEADER_ALIASES}:
            voucher_type_idx = idx if voucher_type_idx is None else voucher_type_idx
        if voucher_date_idx is None and any(hint in header_text or hint in normalized for hint in _DATE_HEADER_HINTS):
            voucher_date_idx = idx

    return voucher_no_idx, voucher_type_idx, voucher_date_idx


def _reset_voucher_state() -> tuple[str, str, str]:
    return "", "", ""


def forward_fill_voucher_columns(frame: pd.DataFrame, headers: list[str]) -> pd.DataFrame:
    """
    对凭证号/凭证字/凭证日期列做纵向 forward-fill（合并单元格续行）。

    续行仅首行显示日期/凭证号时：
    - 日期、凭证字、凭证序号向下继承
    - 首列日期变化时视为新凭证，重置凭证序号状态
    """
    if frame.empty or not headers:
        return frame

    filled = frame.copy()
    voucher_no_idx, voucher_type_idx, voucher_date_idx = resolve_voucher_column_indices(headers)

    last_type = ""
    last_serial = ""
    last_composed = ""
    last_filled_date: date | None = None

    for row_idx in range(len(filled)):
        raw_type = filled.iloc[row_idx, voucher_type_idx] if voucher_type_idx is not None else None
        raw_no = filled.iloc[row_idx, voucher_no_idx] if voucher_no_idx is not None else None
        raw_date = filled.iloc[row_idx, voucher_date_idx] if voucher_date_idx is not None else None

        explicit_date = _parse_date_cell(raw_date) if _cell_has_value(raw_date) else None
        if explicit_date and last_filled_date and explicit_date != last_filled_date:
            last_type, last_serial, last_composed = _reset_voucher_state()

        composed, last_type, last_serial, last_composed = resolve_voucher_no_from_parts(
            raw_voucher_no=raw_no,
            raw_voucher_type=raw_type,
            last_type=last_type,
            last_serial=last_serial,
            last_composed=last_composed,
        )

        if voucher_type_idx is not None and last_type:
            filled.iloc[row_idx, voucher_type_idx] = last_type
        if voucher_no_idx is not None and composed:
            filled.iloc[row_idx, voucher_no_idx] = composed

        if voucher_date_idx is not None:
            if explicit_date:
                last_filled_date = explicit_date
                filled.iloc[row_idx, voucher_date_idx] = explicit_date.isoformat()
            elif last_filled_date is not None:
                filled.iloc[row_idx, voucher_date_idx] = last_filled_date.isoformat()

    return filled


def _format_entry_date(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def entry_parse_group_key(entry: dict[str, Any], fallback_idx: int) -> str:
    """解析阶段凭证分组键：优先 parse_group_key，否则 voucher_no|date。"""
    if entry.get("parse_group_key"):
        return str(entry["parse_group_key"])
    voucher_no = entry.get("voucher_no") or f"__no_voucher__:{fallback_idx}"
    date_part = _format_entry_date(entry.get("voucher_date"))
    if date_part:
        return f"{voucher_no}|{date_part}"
    return voucher_no


def assign_parse_group_keys(
    entries: list[dict[str, Any]],
    signals: list[dict[str, bool]] | None = None,
) -> None:
    """
    按文件行顺序推断凭证分组（续行继承 + 日期/凭证号变化开新组）。

    分录行号应在同一 parse_group_key 内从 1 递增。
    """
    group_seq = 0
    current_key = ""
    line_counter: dict[str, int] = {}

    for index, entry in enumerate(entries):
        signal = signals[index] if signals and index < len(signals) else {}
        previous = entries[index - 1] if index > 0 else None
        start_new = index == 0

        if previous and not start_new:
            if signal.get("raw_had_date") and entry.get("voucher_date") != previous.get("voucher_date"):
                start_new = True
            elif signal.get("raw_had_voucher_no") and entry.get("voucher_no") != previous.get("voucher_no"):
                start_new = True
            elif entry.get("voucher_no") and entry.get("voucher_no") != previous.get("voucher_no"):
                start_new = True

        if start_new:
            group_seq += 1
            voucher_no = entry.get("voucher_no") or f"__seq_{group_seq}"
            date_part = _format_entry_date(entry.get("voucher_date"))
            current_key = f"{voucher_no}|{date_part}|g{group_seq}"

        entry["parse_group_key"] = current_key
        line_counter[current_key] = line_counter.get(current_key, 0) + 1
        if not entry.get("entry_line_no"):
            entry["entry_line_no"] = line_counter[current_key]
