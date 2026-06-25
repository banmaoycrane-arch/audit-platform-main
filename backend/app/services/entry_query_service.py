"""会计分录查询服务 — 序时簿筛选与分页。"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.models import AccountingEntry, AccountingPeriod


def _line_amount_filters(query, amount_min: Decimal | float | None, amount_max: Decimal | float | None):
    if amount_min is not None:
        query = query.filter(
            or_(
                AccountingEntry.debit_amount >= amount_min,
                AccountingEntry.credit_amount >= amount_min,
            )
        )
    if amount_max is not None:
        query = query.filter(
            or_(
                and_(AccountingEntry.debit_amount > 0, AccountingEntry.debit_amount <= amount_max),
                and_(AccountingEntry.credit_amount > 0, AccountingEntry.credit_amount <= amount_max),
            )
        )
    return query


def query_chronological_entries(
    db: Session,
    *,
    ledger_id: int,
    period_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    account_code: str | None = None,
    account_name: str | None = None,
    summary: str | None = None,
    voucher_word: str | None = None,
    voucher_no: str | None = None,
    amount_min: Decimal | float | None = None,
    amount_max: Decimal | float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AccountingEntry], int]:
    """按时间顺序查询账套分录，支持常见序时簿筛选条件。"""
    query = db.query(AccountingEntry).filter(AccountingEntry.ledger_id == ledger_id)

    if period_id is not None:
        period = db.get(AccountingPeriod, period_id)
        if period is not None:
            query = query.filter(
                AccountingEntry.voucher_date >= period.start_date,
                AccountingEntry.voucher_date <= period.end_date,
            )

    if date_from is not None:
        query = query.filter(AccountingEntry.voucher_date >= date_from)
    if date_to is not None:
        query = query.filter(AccountingEntry.voucher_date <= date_to)

    if account_code:
        query = query.filter(AccountingEntry.account_code.contains(account_code.strip()))
    if account_name:
        query = query.filter(AccountingEntry.account_name.contains(account_name.strip()))
    if summary:
        query = query.filter(AccountingEntry.summary.contains(summary.strip()))

    if voucher_word:
        word = voucher_word.strip()
        query = query.filter(
            or_(
                AccountingEntry.voucher_no.like(f"{word}-%"),
                AccountingEntry.voucher_no.like(f"{word}%"),
            )
        )
    if voucher_no:
        query = query.filter(AccountingEntry.voucher_no.contains(voucher_no.strip()))

    query = _line_amount_filters(query, amount_min, amount_max)

    total = query.count()
    items = (
        query.order_by(
            AccountingEntry.voucher_date.asc(),
            AccountingEntry.voucher_no.asc(),
            AccountingEntry.entry_line_no.asc(),
            AccountingEntry.id.asc(),
        )
        .offset(max(offset, 0))
        .limit(min(max(limit, 1), 500))
        .all()
    )
    return items, total
