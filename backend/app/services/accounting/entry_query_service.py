"""会计分录查询服务 — 序时簿筛选与凭证聚合查询。"""
from __future__ import annotations

import json
from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, or_, tuple_
from sqlalchemy.orm import Session, aliased

from app.db.models import AccountingEntry, AccountingPeriod, EntryTag, TagCategory
from app.services.accounting.voucher_card_resolver import (
    resolve_voucher_card_fields,
    resolve_voucher_card_fields_from_slim_rows,
)

VOUCHER_QUERY_PAGE_MAX = 500


@dataclass
class VoucherGroup:
    voucher_id: int | None = None
    voucher_no: str | None = None
    voucher_date: date | None = None
    status: str | None = None
    lines: list[AccountingEntry] = field(default_factory=list)
    debit_total_cached: Decimal | None = field(default=None, repr=False)
    credit_total_cached: Decimal | None = field(default=None, repr=False)
    summary_preview_cached: str | None = field(default=None, repr=False)
    line_count_cached: int | None = field(default=None, repr=False)

    @property
    def line_count(self) -> int:
        if self.line_count_cached is not None:
            return self.line_count_cached
        return len(self.lines)

    @property
    def debit_total(self) -> Decimal:
        if self.debit_total_cached is not None:
            return self.debit_total_cached
        total = Decimal("0.00")
        for line in self.lines:
            total += Decimal(str(line.debit_amount or Decimal("0.00")))
        return total

    @property
    def credit_total(self) -> Decimal:
        if self.credit_total_cached is not None:
            return self.credit_total_cached
        total = Decimal("0.00")
        for line in self.lines:
            total += Decimal(str(line.credit_amount or Decimal("0.00")))
        return total

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


def _account_code_filter_clause(account_code: str, match_mode: str = "contains", column: Any = None):
    """科目编码筛选：exact 精确、prefix 本级及下级、contains 模糊。"""
    col = column or AccountingEntry.account_code
    code = account_code.strip()
    mode = (match_mode or "contains").strip().lower()
    if mode == "exact":
        return col == code
    if mode == "prefix":
        # 序时簿常见扁平编码：1002 的下级为 100201、100202（无点号分隔）
        return or_(
            col == code,
            col.like(f"{code}%"),
        )
    return col.contains(code)


def _apply_account_codes_filter(
    query: Any,
    account_codes: list[str] | None,
    match_mode: str = "contains",
    column: Any = None,
) -> Any:
    codes = [str(code).strip() for code in (account_codes or []) if str(code).strip()]
    if not codes:
        return query
    if len(codes) == 1:
        return query.filter(_account_code_filter_clause(codes[0], match_mode, column))
    col = column or AccountingEntry.account_code
    return query.filter(
        or_(*[_account_code_filter_clause(code, match_mode, col) for code in codes])
    )


def parse_account_codes(
    raw: str | None,
    *,
    fallback: str | None = None,
) -> list[str]:
    if raw:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, list):
            return list(dict.fromkeys(str(item).strip() for item in payload if str(item).strip()))
    if fallback and str(fallback).strip():
        return [str(fallback).strip()]
    return []


def parse_tag_filters(raw: str | None) -> list[dict[str, Any]]:
    """解析 tag_filters JSON，支持 tag_value 单值或 tag_values 多值（筛选时均为 OR）。"""
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        category_code = str(item.get("category_code") or item.get("categoryCode") or "").strip()
        if not category_code:
            continue
        tag_values = item.get("tag_values") or item.get("tagValues")
        values: list[str] = []
        if isinstance(tag_values, list):
            values.extend(str(v).strip() for v in tag_values if str(v).strip())
        tag_value = str(item.get("tag_value") or item.get("tagValue") or "").strip()
        if tag_value:
            values.append(tag_value)
        values = list(dict.fromkeys(values))
        if not values:
            continue
        if len(values) == 1:
            rows.append({"category_code": category_code, "tag_value": values[0]})
        else:
            rows.append({"category_code": category_code, "tag_values": values})
    return rows


def _tag_value_match_filter(tag_alias: Any, value: str) -> Any:
    value = value.strip()
    return or_(
        tag_alias.tag_value == value,
        tag_alias.display_name == value,
        tag_alias.tag_value_normalized == value.lower(),
    )


def _entry_tag_value_exists(
    db: Session,
    *,
    ledger_id: int,
    category_id: int,
    tag_value: str,
) -> Any:
    value = tag_value.strip()
    if not value:
        return None
    tag_alias = aliased(EntryTag)
    return (
        db.query(tag_alias.id)
        .filter(
            tag_alias.entry_id == AccountingEntry.id,
            tag_alias.ledger_id == ledger_id,
            tag_alias.category_id == category_id,
            _tag_value_match_filter(tag_alias, value),
        )
        .correlate(AccountingEntry)
        .exists()
    )


def _voucher_tag_value_exists(
    db: Session,
    *,
    ledger_id: int,
    category_id: int,
    tag_value: str,
) -> Any:
    """同凭证任一分录行上的 tag 命中即视为当前行命中（用于明细账对方科目维度）。"""
    value = tag_value.strip()
    if not value:
        return None
    tag_alias = aliased(EntryTag)
    peer_alias = aliased(AccountingEntry)
    return (
        db.query(tag_alias.id)
        .join(peer_alias, peer_alias.id == tag_alias.entry_id)
        .filter(
            peer_alias.ledger_id == ledger_id,
            AccountingEntry.voucher_no.isnot(None),
            AccountingEntry.voucher_no != "",
            peer_alias.voucher_no == AccountingEntry.voucher_no,
            peer_alias.voucher_date == AccountingEntry.voucher_date,
            tag_alias.ledger_id == ledger_id,
            tag_alias.category_id == category_id,
            _tag_value_match_filter(tag_alias, value),
        )
        .correlate(AccountingEntry)
        .exists()
    )


def _apply_entry_tag_filters(
    db: Session,
    query: Any,
    *,
    ledger_id: int,
    tag_filters: list[dict[str, Any]] | None,
    tag_match_scope: str = "entry",
) -> Any:
    """按 tag 筛选：所有已选 tag（含跨维度）之间为 OR。tag_match_scope=voucher 时按整凭证匹配。"""
    if not tag_filters:
        return query
    grouped: dict[str, list[str]] = {}
    for item in tag_filters:
        category_code = str(item.get("category_code") or "").strip()
        if not category_code:
            continue
        values: list[str] = []
        raw_values = item.get("tag_values")
        if isinstance(raw_values, list):
            values.extend(str(v).strip() for v in raw_values if str(v).strip())
        single = str(item.get("tag_value") or "").strip()
        if single:
            values.append(single)
        if not values:
            continue
        bucket = grouped.setdefault(category_code, [])
        for value in values:
            if value not in bucket:
                bucket.append(value)

    category_id_cache: dict[str, int | None] = {}
    exists_parts: list[Any] = []
    for category_code, values in grouped.items():
        if category_code not in category_id_cache:
            category_id_cache[category_code] = (
                db.query(TagCategory.id)
                .filter(
                    TagCategory.ledger_id == ledger_id,
                    TagCategory.code == category_code,
                )
                .scalar()
            )
        category_id = category_id_cache[category_code]
        if not category_id:
            continue
        exists_fn = _voucher_tag_value_exists if tag_match_scope == "voucher" else _entry_tag_value_exists
        for value in values:
            exists_clause = exists_fn(
                db,
                ledger_id=ledger_id,
                category_id=category_id,
                tag_value=value,
            )
            if exists_clause is not None:
                exists_parts.append(exists_clause)

    if not exists_parts:
        return query
    if len(exists_parts) == 1:
        return query.filter(exists_parts[0])
    return query.filter(or_(*exists_parts))


def _apply_entry_tag_filter(
    db: Session,
    query: Any,
    *,
    ledger_id: int,
    tag_category_code: str | None,
    tag_value: str | None,
) -> Any:
    if not tag_category_code or not tag_value:
        return query
    category_id = (
        db.query(TagCategory.id)
        .filter(
            TagCategory.ledger_id == ledger_id,
            TagCategory.code == tag_category_code.strip(),
        )
        .scalar()
    )
    if not category_id:
        return query.filter(AccountingEntry.id == -1)
    tag_alias = aliased(EntryTag)
    value = tag_value.strip()
    exists_q = (
        db.query(tag_alias.id)
        .filter(
            tag_alias.entry_id == AccountingEntry.id,
            tag_alias.ledger_id == ledger_id,
            tag_alias.category_id == category_id,
            or_(
                tag_alias.tag_value == value,
                tag_alias.display_name == value,
                tag_alias.tag_value_normalized == value.lower(),
            ),
        )
        .correlate(AccountingEntry)
        .exists()
    )
    return query.filter(exists_q)


def _apply_entry_line_sql_filters(
    query: Any,
    *,
    account_code: str | None,
    account_code_match: str = "contains",
    account_name: str | None,
    summary: str | None,
    voucher_word: str | None,
    voucher_no: str | None,
    debit_min: Decimal | float | None,
    debit_max: Decimal | float | None,
    credit_min: Decimal | float | None,
    credit_max: Decimal | float | None,
) -> Any:
    if account_code:
        query = query.filter(_account_code_filter_clause(account_code, account_code_match))
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
    query: Any,
    *,
    ledger_id: int,
    account_code: str | None,
    account_code_match: str = "contains",
    account_name: str | None,
    summary: str | None,
) -> Any:
    line_alias = aliased(AccountingEntry)
    if account_code:
        code_clause = _account_code_filter_clause(account_code, account_code_match, line_alias.account_code)
        exists_q = (
            db.query(line_alias.id)
            .filter(
                line_alias.ledger_id == ledger_id,
                line_alias.voucher_no == AccountingEntry.voucher_no,
                line_alias.voucher_date == AccountingEntry.voucher_date,
                code_clause,
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


def _distinct_voucher_keys_query(query: Any) -> Any:
    return query.with_entities(
        AccountingEntry.voucher_no,
        AccountingEntry.voucher_date,
    ).distinct()


def _count_query_rows(db: Session, query: Any) -> int:
    return db.query(func.count()).select_from(query.subquery()).scalar() or 0


def _paginate_voucher_keys(db: Session, keys_query: Any, offset: int, limit: int) -> Any:
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

    buckets: dict[tuple[str | None, date | None], list[Any]] = defaultdict(list)
    for row in slim_rows:
        buckets[(row.voucher_no, row.voucher_date)].append(row)

    groups: list[VoucherGroup] = []
    for (voucher_no, voucher_date), rows in buckets.items():
        debit_total: Decimal = Decimal("0.00")
        credit_total: Decimal = Decimal("0.00")
        for row in rows:
            debit_total += row.debit_amount or Decimal("0.00")
            credit_total += row.credit_amount or Decimal("0.00")
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
    import_job_id: int | None,
    review_status: str | None,
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
    scoped = _apply_entry_meta_filters(
        scoped,
        import_job_id=import_job_id,
        review_status=review_status,
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
    import_job_id: int | None,
    review_status: str | None,
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
    scoped = _apply_entry_meta_filters(
        scoped,
        import_job_id=import_job_id,
        review_status=review_status,
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


def _line_amount_filters(query: Any, amount_min: Decimal | float | None, amount_max: Decimal | float | None) -> Any:
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


def _apply_entry_meta_filters(
    query: Any,
    *,
    import_job_id: int | None,
    review_status: str | None,
) -> Any:
    if import_job_id is not None:
        query = query.filter(AccountingEntry.import_job_id == import_job_id)
    if review_status:
        query = query.filter(AccountingEntry.review_status == review_status.strip())
    return query


def parse_period_ids(
    raw: str | None,
    *,
    fallback: int | None = None,
) -> list[int]:
    if raw:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, list):
            ids: list[int] = []
            for item in payload:
                try:
                    ids.append(int(item))
                except (TypeError, ValueError):
                    continue
            return list(dict.fromkeys(ids))
    if fallback is not None:
        return [fallback]
    return []


def _apply_scope_filters(
    query: Any,
    *,
    period_id: int | None,
    period_ids: list[int] | None = None,
    date_from: date | None,
    date_to: date | None,
    month: str | None,
    db: Session,
) -> Any:
    if month:
        date_from, date_to = _parse_month(month)

    resolved_period_ids = list(period_ids or [])
    if period_id is not None and period_id not in resolved_period_ids:
        resolved_period_ids.append(period_id)

    if resolved_period_ids and date_from is None and date_to is None:
        periods = (
            db.query(AccountingPeriod)
            .filter(AccountingPeriod.id.in_(resolved_period_ids))
            .all()
        )
        if periods:
            query = query.filter(
                or_(
                    *[
                        and_(
                            AccountingEntry.voucher_date >= period.start_date,
                            AccountingEntry.voucher_date <= period.end_date,
                        )
                        for period in periods
                    ]
                )
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
    period_ids: list[int] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    account_code: str | None = None,
    account_codes: list[str] | None = None,
    account_code_match: str = "contains",
    account_name: str | None = None,
    summary: str | None = None,
    voucher_word: str | None = None,
    voucher_no: str | None = None,
    amount_min: Decimal | float | None = None,
    amount_max: Decimal | float | None = None,
    tag_category_code: str | None = None,
    tag_value: str | None = None,
    tag_filters: list[dict[str, Any]] | None = None,
    counterparty: str | None = None,
    limit: int = 50,
    offset: int = 0,
    tag_match_scope: str = "entry",
) -> tuple[list[AccountingEntry], int]:
    """按时间顺序查询账簿分录，支持常见序时簿筛选条件。"""
    query = db.query(AccountingEntry).filter(AccountingEntry.ledger_id == ledger_id)

    query = _apply_scope_filters(
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
    if account_name:
        query = query.filter(AccountingEntry.account_name.contains(account_name.strip()))
    if summary:
        query = query.filter(AccountingEntry.summary.contains(summary.strip()))
    if counterparty:
        query = query.filter(AccountingEntry.counterparty.contains(counterparty.strip()))

    filters: list[dict[str, Any]] = list(tag_filters or [])
    if tag_category_code and tag_value:
        filters.append(
            {"category_code": tag_category_code.strip(), "tag_value": tag_value.strip()}
        )
    query = _apply_entry_tag_filters(
        db,
        query,
        ledger_id=ledger_id,
        tag_filters=filters,
        tag_match_scope=tag_match_scope,
    )

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
    import_job_id: int | None = None,
    review_status: str | None = None,
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
        "import_job_id": import_job_id,
        "review_status": review_status,
    }
    common_kwargs: dict[str, Any] = {
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
        groups, total = _query_vouchers_voucher_mode(
            db,
            ledger_id=ledger_id,
            total_min=total_min,
            total_max=total_max,
            **common_kwargs,
        )
    else:
        groups, total = _query_vouchers_line_mode(db, ledger_id=ledger_id, **common_kwargs)

    return groups, total
