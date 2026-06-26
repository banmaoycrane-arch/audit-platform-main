"""会计分录查询服务 — 序时簿筛选与凭证聚合查询。"""
from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.models import AccountingEntry, AccountingPeriod


@dataclass
class VoucherGroup:
    voucher_no: str | None
    voucher_date: date | None
    lines: list[AccountingEntry]

    @property
    def debit_total(self) -> float:
        return sum(float(line.debit_amount or 0) for line in self.lines)

    @property
    def credit_total(self) -> float:
        return sum(float(line.credit_amount or 0) for line in self.lines)

    @property
    def summary_preview(self) -> str:
        for line in self.lines:
            if line.summary:
                return str(line.summary)
        return ""


def _voucher_key(entry: AccountingEntry) -> tuple[str, date | None]:
    return (entry.voucher_no or "", entry.voucher_date)


def _parse_month(month: str) -> tuple[date, date]:
    year_str, month_str = month.split("-", 1)
    year = int(year_str)
    mon = int(month_str)
    last_day = monthrange(year, mon)[1]
    return date(year, mon, 1), date(year, mon, last_day)


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


def _apply_scope_filters(
    query,
    *,
    period_id: int | None,
    date_from: date | None,
    date_to: date | None,
    month: str | None,
    db: Session,
):
    if month:
        date_from, date_to = _parse_month(month)

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
    return query


def _line_matches_filters(
    entry: AccountingEntry,
    *,
    account_code: str | None,
    account_name: str | None,
    summary: str | None,
    voucher_word: str | None,
    voucher_no: str | None,
    debit_min: Decimal | float | None,
    debit_max: Decimal | float | None,
    credit_min: Decimal | float | None,
    credit_max: Decimal | float | None,
) -> bool:
    if account_code and account_code.strip() not in (entry.account_code or ""):
        return False
    if account_name and account_name.strip() not in (entry.account_name or ""):
        return False
    if summary and summary.strip() not in (entry.summary or ""):
        return False
    if voucher_no and voucher_no.strip() not in (entry.voucher_no or ""):
        return False
    if voucher_word:
        word = voucher_word.strip()
        voucher = entry.voucher_no or ""
        if not (voucher.startswith(f"{word}-") or voucher.startswith(word)):
            return False
    debit = float(entry.debit_amount or 0)
    credit = float(entry.credit_amount or 0)
    if debit_min is not None and debit > 0 and debit < float(debit_min):
        return False
    if debit_max is not None and debit > 0 and debit > float(debit_max):
        return False
    if credit_min is not None and credit > 0 and credit < float(credit_min):
        return False
    if credit_max is not None and credit > 0 and credit > float(credit_max):
        return False
    if debit_min is not None and debit <= 0 and credit <= 0:
        return False
    return True


def _voucher_matches_filters(
    group: VoucherGroup,
    *,
    account_code: str | None,
    account_name: str | None,
    summary: str | None,
    voucher_word: str | None,
    voucher_no: str | None,
    debit_min: Decimal | float | None,
    debit_max: Decimal | float | None,
    credit_min: Decimal | float | None,
    credit_max: Decimal | float | None,
    total_min: Decimal | float | None,
    total_max: Decimal | float | None,
) -> bool:
    if voucher_no and voucher_no.strip() not in (group.voucher_no or ""):
        return False
    if voucher_word:
        word = voucher_word.strip()
        voucher = group.voucher_no or ""
        if not (voucher.startswith(f"{word}-") or voucher.startswith(word)):
            return False
    if account_code and not any(
        account_code.strip() in (line.account_code or "") for line in group.lines
    ):
        return False
    if account_name and not any(
        account_name.strip() in (line.account_name or "") for line in group.lines
    ):
        return False
    if summary and not any(summary.strip() in (line.summary or "") for line in group.lines):
        return False

    debit_total = group.debit_total
    credit_total = group.credit_total
    voucher_total = max(debit_total, credit_total)

    if debit_min is not None and debit_total < float(debit_min):
        return False
    if debit_max is not None and debit_total > float(debit_max):
        return False
    if credit_min is not None and credit_total < float(credit_min):
        return False
    if credit_max is not None and credit_total > float(credit_max):
        return False
    if total_min is not None and voucher_total < float(total_min):
        return False
    if total_max is not None and voucher_total > float(total_max):
        return False
    return True


def _group_entries(entries: list[AccountingEntry]) -> list[VoucherGroup]:
    buckets: dict[tuple[str, date | None], list[AccountingEntry]] = defaultdict(list)
    for entry in entries:
        buckets[_voucher_key(entry)].append(entry)

    groups: list[VoucherGroup] = []
    for (voucher_no, voucher_date), lines in buckets.items():
        lines.sort(key=lambda row: (row.entry_line_no, row.id))
        groups.append(
            VoucherGroup(
                voucher_no=voucher_no or None,
                voucher_date=voucher_date,
                lines=lines,
            )
        )
    groups.sort(key=lambda group: (group.voucher_date or date.min, group.voucher_no or ""))
    return groups


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

    query = _apply_scope_filters(
        query,
        period_id=period_id,
        date_from=date_from,
        date_to=date_to,
        month=None,
        db=db,
    )

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


def query_vouchers(
    db: Session,
    *,
    ledger_id: int,
    period_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    month: str | None = None,
    filter_mode: str = "line",
    account_code: str | None = None,
    account_name: str | None = None,
    summary: str | None = None,
    voucher_word: str | None = None,
    voucher_no: str | None = None,
    debit_min: Decimal | float | None = None,
    debit_max: Decimal | float | None = None,
    credit_min: Decimal | float | None = None,
    credit_max: Decimal | float | None = None,
    total_min: Decimal | float | None = None,
    total_max: Decimal | float | None = None,
    limit: int = 10,
    offset: int = 0,
) -> tuple[list[VoucherGroup], int]:
    """按凭证聚合查询，支持按行或按凭证整体筛选。"""
    query = db.query(AccountingEntry).filter(AccountingEntry.ledger_id == ledger_id)
    query = _apply_scope_filters(
        query,
        period_id=period_id,
        date_from=date_from,
        date_to=date_to,
        month=month,
        db=db,
    )
    entries = query.order_by(
        AccountingEntry.voucher_date.asc(),
        AccountingEntry.voucher_no.asc(),
        AccountingEntry.entry_line_no.asc(),
        AccountingEntry.id.asc(),
    ).all()

    groups = _group_entries(entries)
    filter_kwargs = {
        "account_code": account_code,
        "account_name": account_name,
        "summary": summary,
        "voucher_word": voucher_word,
        "voucher_no": voucher_no,
        "debit_min": debit_min,
        "debit_max": debit_max,
        "credit_min": credit_min,
        "credit_max": credit_max,
        "total_min": total_min,
        "total_max": total_max,
    }

    matched: list[VoucherGroup] = []
    for group in groups:
        if filter_mode == "voucher":
            if _voucher_matches_filters(group, **filter_kwargs):
                matched.append(group)
            continue

        matched_lines = [
            line
            for line in group.lines
            if _line_matches_filters(
                line,
                account_code=account_code,
                account_name=account_name,
                summary=summary,
                voucher_word=voucher_word,
                voucher_no=voucher_no,
                debit_min=debit_min,
                debit_max=debit_max,
                credit_min=credit_min,
                credit_max=credit_max,
            )
        ]
        if not matched_lines:
            continue
        matched.append(group)

    total = len(matched)
    page = matched[max(offset, 0) : max(offset, 0) + min(max(limit, 1), 100)]
    return page, total
