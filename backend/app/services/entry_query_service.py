"""会计分录查询服务 — 序时簿筛选与凭证聚合查询。"""
from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, or_, tuple_
from sqlalchemy.orm import Session, aliased

from app.db.models import AccountingEntry, AccountingPeriod
from app.services.voucher_card_resolver import (
    resolve_voucher_card_fields,
    resolve_voucher_card_fields_from_slim_rows,
)


@dataclass
class VoucherGroup:
    voucher_id: int | None = None
    voucher_no: str | None = None
    voucher_date: date | None = None
    status: str | None = None
    lines: list[AccountingEntry] = field(default_factory=list)
    debit_total_cached: float | None = field(default=None, repr=False)
    credit_total_cached: float | None = field(default=None, repr=False)
    summary_preview_cached: str | None = field(default=None, repr=False)
    line_count_cached: int | None = field(default=None, repr=False)

    @property
    def line_count(self) -> int:
        if self.line_count_cached is not None:
            return self.line_count_cached
        return len(self.lines)

    @property
    def debit_total(self) -> float:
        if self.debit_total_cached is not None:
            return self.debit_total_cached
        return sum(float(line.debit_amount or 0) for line in self.lines)

    @property
    def credit_total(self) -> float:
        if self.credit_total_cached is not None:
            return self.credit_total_cached
        return sum(float(line.credit_amount or 0) for line in self.lines)

    @property
    def summary_preview(self) -> str:
        if self.summary_preview_cached is not None:
            return self.summary_preview_cached
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


def _apply_entry_line_sql_filters(
    query,
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
):
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
    if debit_min is not None:
        query = query.filter(AccountingEntry.debit_amount >= debit_min)
    if debit_max is not None:
        query = query.filter(
            and_(AccountingEntry.debit_amount > 0, AccountingEntry.debit_amount <= debit_max)
        )
    if credit_min is not None:
        query = query.filter(AccountingEntry.credit_amount >= credit_min)
    if credit_max is not None:
        query = query.filter(
            and_(AccountingEntry.credit_amount > 0, AccountingEntry.credit_amount <= credit_max)
        )
    return query


def _apply_voucher_exists_line_filters(
    db: Session,
    query,
    *,
    ledger_id: int,
    account_code: str | None,
    account_name: str | None,
    summary: str | None,
):
    line_alias = aliased(AccountingEntry)
    if account_code:
        exists_q = (
            db.query(line_alias.id)
            .filter(
                line_alias.ledger_id == ledger_id,
                line_alias.voucher_no == AccountingEntry.voucher_no,
                line_alias.voucher_date == AccountingEntry.voucher_date,
                line_alias.account_code.contains(account_code.strip()),
            )
            .correlate(AccountingEntry)
            .exists()
        )
        query = query.filter(exists_q)
    if account_name:
        exists_q = (
            db.query(line_alias.id)
            .filter(
                line_alias.ledger_id == ledger_id,
                line_alias.voucher_no == AccountingEntry.voucher_no,
                line_alias.voucher_date == AccountingEntry.voucher_date,
                line_alias.account_name.contains(account_name.strip()),
            )
            .correlate(AccountingEntry)
            .exists()
        )
        query = query.filter(exists_q)
    if summary:
        exists_q = (
            db.query(line_alias.id)
            .filter(
                line_alias.ledger_id == ledger_id,
                line_alias.voucher_no == AccountingEntry.voucher_no,
                line_alias.voucher_date == AccountingEntry.voucher_date,
                line_alias.summary.contains(summary.strip()),
            )
            .correlate(AccountingEntry)
            .exists()
        )
        query = query.filter(exists_q)
    return query


def _distinct_voucher_keys_query(query):
    return query.with_entities(
        AccountingEntry.voucher_no,
        AccountingEntry.voucher_date,
    ).distinct()


def _count_query_rows(db: Session, query) -> int:
    return db.query(func.count()).select_from(query.subquery()).scalar() or 0


def _paginate_voucher_keys(db: Session, keys_query, offset: int, limit: int):
    subq = keys_query.subquery()
    safe_limit = min(max(limit, 1), 500)
    safe_offset = max(offset, 0)
    return (
        db.query(subq.c.voucher_no, subq.c.voucher_date)
        .order_by(subq.c.voucher_date.asc(), subq.c.voucher_no.asc())
        .offset(safe_offset)
        .limit(safe_limit)
        .all()
    )


def _load_summaries_for_keys(
    db: Session,
    *,
    ledger_id: int,
    keys: list[tuple[str | None, date | None]],
    period_id: int | None,
    date_from: date | None,
    date_to: date | None,
    month: str | None,
) -> list[VoucherGroup]:
    """仅加载凭证摘要字段，不加载完整分录行（列表接口性能优化）。"""
    if not keys:
        return []

    scoped = db.query(AccountingEntry).filter(AccountingEntry.ledger_id == ledger_id)
    scoped = _apply_scope_filters(
        scoped,
        period_id=period_id,
        date_from=date_from,
        date_to=date_to,
        month=month,
        db=db,
    )
    slim_rows = (
        scoped.filter(tuple_(AccountingEntry.voucher_no, AccountingEntry.voucher_date).in_(keys))
        .with_entities(
            AccountingEntry.voucher_no,
            AccountingEntry.voucher_date,
            AccountingEntry.debit_amount,
            AccountingEntry.credit_amount,
            AccountingEntry.summary,
            AccountingEntry.entry_line_no,
        )
        .order_by(
            AccountingEntry.voucher_date.asc(),
            AccountingEntry.voucher_no.asc(),
            AccountingEntry.entry_line_no.asc(),
            AccountingEntry.id.asc(),
        )
        .all()
    )

    buckets: dict[tuple[str | None, date | None], list] = defaultdict(list)
    for row in slim_rows:
        buckets[(row.voucher_no, row.voucher_date)].append(row)

    groups: list[VoucherGroup] = []
    for (voucher_no, voucher_date), rows in buckets.items():
        debit_total = sum(float(row.debit_amount or 0) for row in rows)
        credit_total = sum(float(row.credit_amount or 0) for row in rows)
        summary_preview = ""
        for row in sorted(rows, key=lambda item: (item.entry_line_no or 0)):
            if row.summary:
                summary_preview = str(row.summary)
                break
        voucher_id, voucher_status = resolve_voucher_card_fields_from_slim_rows(
            db, ledger_id, voucher_no, voucher_date, rows
        )
        groups.append(
            VoucherGroup(
                voucher_id=voucher_id,
                status=voucher_status,
                voucher_no=voucher_no or None,
                voucher_date=voucher_date,
                lines=[],
                debit_total_cached=debit_total,
                credit_total_cached=credit_total,
                summary_preview_cached=summary_preview,
                line_count_cached=len(rows),
            )
        )

    order_map = {key: index for index, key in enumerate(keys)}
    groups.sort(key=lambda group: order_map.get((group.voucher_no, group.voucher_date), 10**9))
    return groups


def _load_groups_for_keys(
    db: Session,
    *,
    ledger_id: int,
    keys: list[tuple[str | None, date | None]],
    period_id: int | None,
    date_from: date | None,
    date_to: date | None,
    month: str | None,
) -> list[VoucherGroup]:
    if not keys:
        return []

    scoped = db.query(AccountingEntry).filter(AccountingEntry.ledger_id == ledger_id)
    scoped = _apply_scope_filters(
        scoped,
        period_id=period_id,
        date_from=date_from,
        date_to=date_to,
        month=month,
        db=db,
    )
    scoped = scoped.filter(tuple_(AccountingEntry.voucher_no, AccountingEntry.voucher_date).in_(keys))
    entries = scoped.order_by(
        AccountingEntry.voucher_date.asc(),
        AccountingEntry.voucher_no.asc(),
        AccountingEntry.entry_line_no.asc(),
        AccountingEntry.id.asc(),
    ).all()
    groups = _group_entries(db, ledger_id, entries)
    order_map = {key: index for index, key in enumerate(keys)}
    groups.sort(key=lambda group: order_map.get((group.voucher_no, group.voucher_date), 10**9))
    return groups


def load_voucher_lines(
    db: Session,
    *,
    ledger_id: int,
    voucher_no: str | None,
    voucher_date: date | None,
) -> list[AccountingEntry]:
    """加载单张凭证的全部分录行。"""
    query = db.query(AccountingEntry).filter(AccountingEntry.ledger_id == ledger_id)
    if voucher_no:
        query = query.filter(AccountingEntry.voucher_no == voucher_no)
    else:
        query = query.filter(or_(AccountingEntry.voucher_no.is_(None), AccountingEntry.voucher_no == ""))
    if voucher_date is not None:
        query = query.filter(AccountingEntry.voucher_date == voucher_date)
    else:
        query = query.filter(AccountingEntry.voucher_date.is_(None))
    return query.order_by(
        AccountingEntry.entry_line_no.asc(),
        AccountingEntry.id.asc(),
    ).all()


def _load_groups_for_page(
    db: Session,
    *,
    ledger_id: int,
    keys: list[tuple[str | None, date | None]],
    period_id: int | None,
    date_from: date | None,
    date_to: date | None,
    month: str | None,
    include_lines: bool,
) -> list[VoucherGroup]:
    if include_lines:
        return _load_groups_for_keys(
            db,
            ledger_id=ledger_id,
            keys=keys,
            period_id=period_id,
            date_from=date_from,
            date_to=date_to,
            month=month,
        )
    return _load_summaries_for_keys(
        db,
        ledger_id=ledger_id,
        keys=keys,
        period_id=period_id,
        date_from=date_from,
        date_to=date_to,
        month=month,
    )


def _query_vouchers_line_mode(
    db: Session,
    *,
    ledger_id: int,
    period_id: int | None,
    date_from: date | None,
    date_to: date | None,
    month: str | None,
    account_code: str | None,
    account_name: str | None,
    summary: str | None,
    voucher_word: str | None,
    voucher_no: str | None,
    debit_min: Decimal | float | None,
    debit_max: Decimal | float | None,
    credit_min: Decimal | float | None,
    credit_max: Decimal | float | None,
    limit: int,
    offset: int,
    include_lines: bool = False,
) -> tuple[list[VoucherGroup], int]:
    scoped = db.query(AccountingEntry).filter(AccountingEntry.ledger_id == ledger_id)
    scoped = _apply_scope_filters(
        scoped,
        period_id=period_id,
        date_from=date_from,
        date_to=date_to,
        month=month,
        db=db,
    )
    line_query = _apply_entry_line_sql_filters(
        scoped,
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
    keys_query = _distinct_voucher_keys_query(line_query)
    total = _count_query_rows(db, keys_query)
    keys = _paginate_voucher_keys(db, keys_query, offset, limit)
    groups = _load_groups_for_page(
        db,
        ledger_id=ledger_id,
        keys=keys,
        period_id=period_id,
        date_from=date_from,
        date_to=date_to,
        month=month,
        include_lines=include_lines,
    )
    return groups, total


def _query_vouchers_voucher_mode(
    db: Session,
    *,
    ledger_id: int,
    period_id: int | None,
    date_from: date | None,
    date_to: date | None,
    month: str | None,
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
    limit: int,
    offset: int,
    include_lines: bool = False,
) -> tuple[list[VoucherGroup], int]:
    scoped = db.query(AccountingEntry).filter(AccountingEntry.ledger_id == ledger_id)
    scoped = _apply_scope_filters(
        scoped,
        period_id=period_id,
        date_from=date_from,
        date_to=date_to,
        month=month,
        db=db,
    )
    if voucher_no:
        scoped = scoped.filter(AccountingEntry.voucher_no.contains(voucher_no.strip()))
    if voucher_word:
        word = voucher_word.strip()
        scoped = scoped.filter(
            or_(
                AccountingEntry.voucher_no.like(f"{word}-%"),
                AccountingEntry.voucher_no.like(f"{word}%"),
            )
        )
    scoped = _apply_voucher_exists_line_filters(
        db,
        scoped,
        ledger_id=ledger_id,
        account_code=account_code,
        account_name=account_name,
        summary=summary,
    )

    grouped = scoped.with_entities(
        AccountingEntry.voucher_no,
        AccountingEntry.voucher_date,
    ).group_by(AccountingEntry.voucher_no, AccountingEntry.voucher_date)

    if debit_min is not None:
        grouped = grouped.having(func.sum(AccountingEntry.debit_amount) >= debit_min)
    if debit_max is not None:
        grouped = grouped.having(func.sum(AccountingEntry.debit_amount) <= debit_max)
    if credit_min is not None:
        grouped = grouped.having(func.sum(AccountingEntry.credit_amount) >= credit_min)
    if credit_max is not None:
        grouped = grouped.having(func.sum(AccountingEntry.credit_amount) <= credit_max)
    if total_min is not None:
        grouped = grouped.having(func.sum(AccountingEntry.debit_amount) >= total_min)
    if total_max is not None:
        grouped = grouped.having(func.sum(AccountingEntry.debit_amount) <= total_max)

    total = _count_query_rows(db, grouped)
    keys = _paginate_voucher_keys(db, grouped, offset, limit)
    groups = _load_groups_for_page(
        db,
        ledger_id=ledger_id,
        keys=keys,
        period_id=period_id,
        date_from=date_from,
        date_to=date_to,
        month=month,
        include_lines=include_lines,
    )
    return groups, total


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


def _group_entries(
    db: Session,
    ledger_id: int,
    entries: list[AccountingEntry],
) -> list[VoucherGroup]:
    buckets: dict[tuple[str, date | None], list[AccountingEntry]] = defaultdict(list)
    for entry in entries:
        buckets[_voucher_key(entry)].append(entry)

    groups: list[VoucherGroup] = []
    for (voucher_no, voucher_date), lines in buckets.items():
        lines.sort(key=lambda row: (row.entry_line_no, row.id))
        voucher_id, voucher_status = resolve_voucher_card_fields(
            db, ledger_id, voucher_no, voucher_date, lines
        )
        groups.append(
            VoucherGroup(
                voucher_id=voucher_id,
                status=voucher_status,
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
    """按时间顺序查询账簿分录，支持常见序时簿筛选条件。"""
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
    include_lines: bool = False,
) -> tuple[list[VoucherGroup], int]:
    """按凭证聚合查询，支持按行或按凭证整体筛选。"""
    scope_kwargs = {
        "period_id": period_id,
        "date_from": date_from,
        "date_to": date_to,
        "month": month,
    }
    common_kwargs = {
        **scope_kwargs,
        "account_code": account_code,
        "account_name": account_name,
        "summary": summary,
        "voucher_word": voucher_word,
        "voucher_no": voucher_no,
        "debit_min": debit_min,
        "debit_max": debit_max,
        "credit_min": credit_min,
        "credit_max": credit_max,
        "limit": limit,
        "offset": offset,
        "include_lines": include_lines,
    }

    if filter_mode == "voucher":
        return _query_vouchers_voucher_mode(
            db,
            ledger_id=ledger_id,
            total_min=total_min,
            total_max=total_max,
            **common_kwargs,
        )

    return _query_vouchers_line_mode(db, ledger_id=ledger_id, **common_kwargs)
