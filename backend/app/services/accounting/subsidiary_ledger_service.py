"""明细账：期初余额计算与 Excel 导出。"""
from __future__ import annotations

import io
import json
from datetime import date
from decimal import Decimal
from typing import Any

from openpyxl import Workbook
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import AccountingEntry, AccountingPeriod, OpeningBalance
from app.services.accounting.entry_query_service import (
    _account_code_filter_clause,
    _apply_account_codes_filter,
    parse_tag_filters,
    query_chronological_entries,
)
from app.services.basic_data import coa_service

# 科目明细账本质：按汇总科目查询，始终含本级及全部下级明细科目分录
SUBSIDIARY_ACCOUNT_MATCH = "prefix"


def normalize_subsidiary_account_match(match_mode: str | None) -> str:
    """明细账固定按科目汇总展开；习惯里保存的 exact 等模式在此统一归一为 prefix。"""
    return SUBSIDIARY_ACCOUNT_MATCH


def _expand_rollup_account_codes(
    db: Session,
    ledger_id: int,
    codes: list[str],
) -> list[str]:
    """展开汇总科目：返回本级 + 账簿中实际存在的全部下级明细科目编码。"""
    if not codes:
        return []
    expanded: set[str] = {code.strip() for code in codes if str(code).strip()}
    rows = (
        db.query(AccountingEntry.account_code)
        .filter(AccountingEntry.ledger_id == ledger_id)
        .distinct()
        .all()
    )
    for (acct_code,) in rows:
        if not acct_code:
            continue
        for code in codes:
            root = str(code).strip()
            if not root:
                continue
            if acct_code == root or acct_code.startswith(root):
                expanded.add(acct_code)
    return sorted(expanded)


def _parse_tag_filters(raw: str | None) -> list[dict[str, Any]]:
    return parse_tag_filters(raw)


def _resolve_account_direction(
    db: Session,
    account_code: str | None,
    ledger_id: int | None = None,
) -> str:
    if not account_code:
        return "debit"
    account = coa_service.get_by_code(db, account_code, ledger_id=ledger_id)
    if account and str(account.direction or "").lower() in {"credit", "贷"}:
        return "credit"
    return "debit"


def _build_base_entry_query(
    db: Session,
    *,
    ledger_id: int,
    account_code: str | None,
    account_codes: list[str] | None,
    account_code_match: str,
    period_id: int | None,
    period_ids: list[int] | None = None,
    date_from: date | None,
    date_to: date | None,
    summary: str | None,
    counterparty: str | None,
    tag_category_code: str | None,
    tag_value: str | None,
    tag_filters: list[dict[str, Any]],
):
    from app.services.accounting import entry_query_service as eqs

    query = db.query(AccountingEntry).filter(AccountingEntry.ledger_id == ledger_id)
    query = eqs._apply_scope_filters(
        query,
        period_id=period_id,
        period_ids=period_ids,
        date_from=date_from,
        date_to=date_to,
        month=None,
        db=db,
    )
    if account_codes:
        query = _apply_account_codes_filter(query, account_codes, account_code_match)
    elif account_code:
        query = query.filter(_account_code_filter_clause(account_code, account_code_match))
    if summary:
        query = query.filter(AccountingEntry.summary.contains(summary.strip()))
    if counterparty:
        query = query.filter(AccountingEntry.counterparty.contains(counterparty.strip()))

    filters = list(tag_filters)
    if tag_category_code and tag_value:
        filters.append({"category_code": tag_category_code.strip(), "tag_value": tag_value.strip()})
    return eqs._apply_entry_tag_filters(
        db, query, ledger_id=ledger_id, tag_filters=filters, tag_match_scope="voucher"
    )


def compute_subsidiary_opening_balance(
    db: Session,
    *,
    ledger_id: int,
    account_code: str | None = None,
    account_codes: list[str] | None = None,
    account_code_match: str = SUBSIDIARY_ACCOUNT_MATCH,
    organization_id: int | None = None,
    period_id: int | None = None,
    period_ids: list[int] | None = None,
    date_from: date | None = None,
    summary: str | None = None,
    counterparty: str | None = None,
    tag_category_code: str | None = None,
    tag_value: str | None = None,
    tag_filters_raw: str | None = None,
) -> dict[str, Any]:
    codes = list(account_codes or [])
    if not codes and account_code:
        codes = [account_code]
    primary_code = codes[0] if codes else account_code
    match_mode = normalize_subsidiary_account_match(account_code_match)
    rollup_codes = _expand_rollup_account_codes(db, ledger_id, codes)
    direction = _resolve_account_direction(db, primary_code, ledger_id=ledger_id)
    tag_filters = _parse_tag_filters(tag_filters_raw)
    balance = Decimal("0.00")

    if organization_id and rollup_codes and (period_id or period_ids):
        target_period_ids = list(period_ids or [])
        if period_id is not None and period_id not in target_period_ids:
            target_period_ids.append(period_id)
        ob_rows = (
            db.query(OpeningBalance)
            .filter(
                OpeningBalance.organization_id == organization_id,
                OpeningBalance.period_id.in_(target_period_ids),
                OpeningBalance.account_code.in_(rollup_codes),
            )
            .all()
        )
        for ob in ob_rows:
            balance += Decimal(str(ob.debit_balance or 0)) - Decimal(str(ob.credit_balance or 0))

    cutoff = date_from
    if cutoff is None and (period_ids or period_id):
        target_period_ids = list(period_ids or [])
        if period_id is not None and period_id not in target_period_ids:
            target_period_ids.append(period_id)
        periods = (
            db.query(AccountingPeriod)
            .filter(AccountingPeriod.id.in_(target_period_ids))
            .all()
        )
        if periods:
            cutoff = min(period.start_date for period in periods)

    if cutoff is not None:
        prior_query = db.query(AccountingEntry).filter(
            AccountingEntry.ledger_id == ledger_id,
            AccountingEntry.voucher_date.isnot(None),
            AccountingEntry.voucher_date < cutoff,
        )
        if codes:
            prior_query = _apply_account_codes_filter(prior_query, codes, match_mode)
        elif account_code:
            prior_query = prior_query.filter(
                _account_code_filter_clause(account_code, match_mode)
            )
        if summary:
            prior_query = prior_query.filter(AccountingEntry.summary.contains(summary.strip()))
        if counterparty:
            prior_query = prior_query.filter(AccountingEntry.counterparty.contains(counterparty.strip()))
        from app.services.accounting import entry_query_service as eqs

        filters = list(tag_filters)
        if tag_category_code and tag_value:
            filters.append(
                {"category_code": tag_category_code.strip(), "tag_value": tag_value.strip()}
            )
        prior_query = eqs._apply_entry_tag_filters(
            db,
            prior_query,
            ledger_id=ledger_id,
            tag_filters=filters,
            tag_match_scope="voucher",
        )
        debit_sum = prior_query.with_entities(
            func.coalesce(func.sum(AccountingEntry.debit_amount), 0)
        ).scalar() or 0
        credit_sum = prior_query.with_entities(
            func.coalesce(func.sum(AccountingEntry.credit_amount), 0)
        ).scalar() or 0
        balance += Decimal(str(debit_sum)) - Decimal(str(credit_sum))

    display_balance = balance if direction == "debit" else -balance
    return {
        "account_code": primary_code,
        "account_codes": codes,
        "direction": direction,
        "opening_balance": float(display_balance.quantize(Decimal("0.01"))),
        "raw_balance": float(balance.quantize(Decimal("0.01"))),
    }


def list_subsidiary_entries(
    db: Session,
    *,
    ledger_id: int,
    account_code: str | None = None,
    account_codes: list[str] | None = None,
    account_code_match: str = SUBSIDIARY_ACCOUNT_MATCH,
    period_id: int | None = None,
    period_ids: list[int] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    summary: str | None = None,
    counterparty: str | None = None,
    tag_category_code: str | None = None,
    tag_value: str | None = None,
    tag_filters_raw: str | None = None,
    limit: int = 2000,
    offset: int = 0,
) -> tuple[list[AccountingEntry], int]:
    match_mode = normalize_subsidiary_account_match(account_code_match)
    tag_filters = _parse_tag_filters(tag_filters_raw)
    codes = list(account_codes or [])
    if not codes and account_code:
        codes = [account_code]
    if tag_filters:
        query = _build_base_entry_query(
            db,
            ledger_id=ledger_id,
            account_code=account_code,
            account_codes=codes or None,
            account_code_match=match_mode,
            period_id=period_id,
            period_ids=period_ids,
            date_from=date_from,
            date_to=date_to,
            summary=summary,
            counterparty=counterparty,
            tag_category_code=tag_category_code,
            tag_value=tag_value,
            tag_filters=tag_filters,
        )
        total = query.count()
        items = (
            query.order_by(
                AccountingEntry.voucher_date.asc(),
                AccountingEntry.voucher_no.asc(),
                AccountingEntry.entry_line_no.asc(),
                AccountingEntry.id.asc(),
            )
            .offset(max(offset, 0))
            .limit(min(max(limit, 1), 5000))
            .all()
        )
        return items, total

    return query_chronological_entries(
        db,
        ledger_id=ledger_id,
        period_id=period_id,
        period_ids=period_ids,
        date_from=date_from,
        date_to=date_to,
        account_code=account_code,
        account_codes=codes or None,
        account_code_match=match_mode,
        summary=summary,
        counterparty=counterparty,
        tag_category_code=tag_category_code,
        tag_value=tag_value,
        tag_filters=tag_filters,
        limit=limit,
        offset=offset,
    )


def export_subsidiary_ledger_xlsx(
    db: Session,
    *,
    ledger_id: int,
    account_code: str | None = None,
    account_codes: list[str] | None = None,
    account_code_match: str = SUBSIDIARY_ACCOUNT_MATCH,
    period_id: int | None = None,
    period_ids: list[int] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    summary: str | None = None,
    counterparty: str | None = None,
    tag_category_code: str | None = None,
    tag_value: str | None = None,
    tag_filters_raw: str | None = None,
    include_subtotals: bool = False,
    subtotal_mode: str = "none",
    custom_days: int = 7,
    opening_balance: float = 0.0,
    direction: str = "debit",
    category_codes: list[str] | None = None,
    ledger_name: str | None = None,
    period_code: str | None = None,
) -> bytes:
    from app.db.models import EntryTag, TagCategory
    from app.services.accounting.report_format_standard import (
        SUBSIDIARY_HEADERS_BASE,
        balance_direction,
        format_money_num,
        report_meta_lines,
    )

    items, _ = list_subsidiary_entries(
        db,
        ledger_id=ledger_id,
        account_code=account_code,
        account_codes=account_codes,
        account_code_match=account_code_match,
        period_id=period_id,
        period_ids=period_ids,
        date_from=date_from,
        date_to=date_to,
        summary=summary,
        counterparty=counterparty,
        tag_category_code=tag_category_code,
        tag_value=tag_value,
        tag_filters_raw=tag_filters_raw,
        limit=5000,
        offset=0,
    )
    entry_ids = [item.id for item in items]
    tags_by_entry: dict[int, dict[str, str]] = {}
    if entry_ids:
        rows = (
            db.query(EntryTag, TagCategory.code)
            .join(TagCategory, EntryTag.category_id == TagCategory.id)
            .filter(EntryTag.entry_id.in_(entry_ids))
            .all()
        )
        for tag, category_code in rows:
            bucket = tags_by_entry.setdefault(tag.entry_id, {})
            bucket[category_code] = tag.display_name or tag.tag_value or ""

    account_label = "、".join(account_codes or []) if account_codes else (account_code or "全部科目")
    wb = Workbook()
    ws = wb.active
    ws.title = "明细账"
    dim_codes = category_codes or []
    headers = [
        *SUBSIDIARY_HEADERS_BASE[:3],
        "科目编码",
        "科目名称",
        *dim_codes,
        *SUBSIDIARY_HEADERS_BASE[3:],
        "往来单位",
    ]
    for meta_row in report_meta_lines(
        report_title="明细分类账",
        ledger_name=ledger_name,
        period_code=period_code,
        as_of_date=date_to,
        account_label=account_label,
    ):
        ws.append(meta_row if isinstance(meta_row, list) else [meta_row])
    ws.append(headers)
    ws.append(
        [
            "",
            "",
            "期初余额",
            account_code or (account_codes[0] if account_codes else ""),
            "",
            *([""] * len(dim_codes)),
            "",
            "",
            "",
            opening_balance,
            "",
        ]
    )

    running = Decimal(str(opening_balance))
    period_debit = Decimal("0")
    period_credit = Decimal("0")
    for entry in items:
        debit = Decimal(str(entry.debit_amount or 0))
        credit = Decimal(str(entry.credit_amount or 0))
        period_debit += debit
        period_credit += credit
        if direction == "credit":
            running += credit - debit
        else:
            running += debit - credit
        row_tags = tags_by_entry.get(entry.id, {})
        ws.append(
            [
                entry.voucher_date.isoformat() if entry.voucher_date else "",
                entry.voucher_no or "",
                entry.summary or "",
                entry.account_code or "",
                entry.account_name or "",
                *[row_tags.get(code, "") for code in dim_codes],
                format_money_num(debit),
                format_money_num(credit),
                balance_direction(running, direction),
                format_money_num(abs(running)),
                entry.counterparty or "",
            ]
        )

    ws.append(
        [
            "",
            "",
            "本期合计",
            "",
            "",
            *([""] * len(dim_codes)),
            format_money_num(period_debit),
            format_money_num(period_credit),
            "",
            format_money_num(abs(running)),
            "",
        ]
    )

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
