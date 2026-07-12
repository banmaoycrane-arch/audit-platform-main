"""审计快照类结构化表解析：科目余额表 / 明细账 / 总账。"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.doc_parsing.day_book_parser import iter_data_row_indices, resolve_structured_table

_ACCOUNT_CODE_ALIASES = ("科目代码", "科目编码", "account_code", "subject_code", "代码")
_ACCOUNT_NAME_ALIASES = ("科目名称", "account_name", "subject_name", "名称")
_OPENING_ALIASES = ("期初余额", "opening_balance", "期初")
_DEBIT_TOTAL_ALIASES = ("借方发生", "借方合计", "借方", "debit_total", "debit")
_CREDIT_TOTAL_ALIASES = ("贷方发生", "贷方合计", "贷方", "credit_total", "credit")
_CLOSING_ALIASES = ("期末余额", "closing_balance", "期末")
_DIRECTION_ALIASES = ("方向", "direction", "余额方向")
_PERIOD_ALIASES = ("期间", "会计期间", "period", "period_code")
_DATE_ALIASES = ("日期", "凭证日期", "date", "voucher_date")
_VOUCHER_NO_ALIASES = ("凭证号", "凭证编号", "voucher_no", "document_no")
_SUMMARY_ALIASES = ("摘要", "summary", "说明")
_RUNNING_BALANCE_ALIASES = ("余额", "running_balance", "balance")


def _normalize_header(value: Any) -> str:
    text = str(value or "").strip().lower()
    return re.sub(r"\s+", "", text)


def _match_column(headers: list[str], aliases: tuple[str, ...]) -> int | None:
    normalized_aliases = {_normalize_header(alias) for alias in aliases}
    for index, header in enumerate(headers):
        normalized = _normalize_header(header)
        if normalized in normalized_aliases:
            return index
        if any(alias in normalized for alias in normalized_aliases if len(alias) >= 2):
            return index
    return None


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "-", "—"}:
        return None
    text = re.sub(r"[¥￥元,\s]", "", text)
    if not text:
        return None
    try:
        return Decimal(text).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def _row_value(row: Any, index: int | None) -> Any:
    if index is None or index >= len(row):
        return None
    return row.iloc[index]


def _parse_rows(path: str) -> tuple[list[str], list[Any], dict[str, Any]]:
    layout = resolve_structured_table(path)
    if layout is None or layout.raw_frame.empty:
        return [], [], {"error": "无法识别结构化表格"}
    headers = [str(h).strip() for h in layout.raw_headers]
    row_indices = list(iter_data_row_indices(layout.raw_frame, layout.header_row_index))
    rows = [layout.raw_frame.iloc[idx] for idx in row_indices]
    metadata = {
        "company_name": layout.metadata.company_name,
        "report_period": layout.metadata.report_period,
        "title": layout.metadata.title,
    }
    return headers, rows, metadata


def parse_account_balance_rows(path: str) -> list[dict[str, Any]]:
    headers, rows, _metadata = _parse_rows(path)
    if not headers:
        return []
    code_idx = _match_column(headers, _ACCOUNT_CODE_ALIASES)
    name_idx = _match_column(headers, _ACCOUNT_NAME_ALIASES)
    opening_idx = _match_column(headers, _OPENING_ALIASES)
    debit_idx = _match_column(headers, _DEBIT_TOTAL_ALIASES)
    credit_idx = _match_column(headers, _CREDIT_TOTAL_ALIASES)
    closing_idx = _match_column(headers, _CLOSING_ALIASES)
    direction_idx = _match_column(headers, _DIRECTION_ALIASES)
    period_idx = _match_column(headers, _PERIOD_ALIASES)

    parsed: list[dict[str, Any]] = []
    for row in rows:
        account_code = _row_value(row, code_idx)
        account_name = _row_value(row, name_idx)
        if not str(account_code or "").strip() and not str(account_name or "").strip():
            continue
        parsed.append(
            {
                "account_code": str(account_code).strip() if account_code is not None else None,
                "account_name": str(account_name).strip() if account_name is not None else None,
                "period_code": str(_row_value(row, period_idx)).strip() if period_idx is not None else None,
                "opening_balance": _parse_decimal(_row_value(row, opening_idx)),
                "debit_total": _parse_decimal(_row_value(row, debit_idx)),
                "credit_total": _parse_decimal(_row_value(row, credit_idx)),
                "closing_balance": _parse_decimal(_row_value(row, closing_idx)),
                "direction": str(_row_value(row, direction_idx)).strip() if direction_idx is not None else None,
            }
        )
    return parsed


def parse_general_ledger_line_rows(path: str) -> list[dict[str, Any]]:
    headers, rows, _metadata = _parse_rows(path)
    if not headers:
        return []
    code_idx = _match_column(headers, _ACCOUNT_CODE_ALIASES)
    name_idx = _match_column(headers, _ACCOUNT_NAME_ALIASES)
    date_idx = _match_column(headers, _DATE_ALIASES)
    voucher_idx = _match_column(headers, _VOUCHER_NO_ALIASES)
    summary_idx = _match_column(headers, _SUMMARY_ALIASES)
    debit_idx = _match_column(headers, _DEBIT_TOTAL_ALIASES)
    credit_idx = _match_column(headers, _CREDIT_TOTAL_ALIASES)
    balance_idx = _match_column(headers, _RUNNING_BALANCE_ALIASES)
    direction_idx = _match_column(headers, _DIRECTION_ALIASES)

    parsed: list[dict[str, Any]] = []
    for row in rows:
        account_code = _row_value(row, code_idx)
        account_name = _row_value(row, name_idx)
        summary = _row_value(row, summary_idx)
        if not any(str(v or "").strip() for v in (account_code, account_name, summary)):
            continue
        parsed.append(
            {
                "account_code": str(account_code).strip() if account_code is not None else None,
                "account_name": str(account_name).strip() if account_name is not None else None,
                "voucher_date": _parse_date(_row_value(row, date_idx)),
                "voucher_no": str(_row_value(row, voucher_idx)).strip() if voucher_idx is not None else None,
                "summary": str(summary).strip() if summary is not None else None,
                "debit": _parse_decimal(_row_value(row, debit_idx)),
                "credit": _parse_decimal(_row_value(row, credit_idx)),
                "running_balance": _parse_decimal(_row_value(row, balance_idx)),
                "direction": str(_row_value(row, direction_idx)).strip() if direction_idx is not None else None,
            }
        )
    return parsed


def parse_general_ledger_summary_rows(path: str) -> list[dict[str, Any]]:
    return parse_account_balance_rows(path)
