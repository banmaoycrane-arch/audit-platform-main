"""Staging 凭证预览：数据库侧 GROUP BY 分页与统计（避免全量载入内存）。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Integer, String, and_, case, cast, func, literal, or_, select
from sqlalchemy.orm import Session

from app.db.models import StagingAccountingEntry
from app.services.audit.staging_review_service import (
    VERIFIED_REVIEW_STATUSES,
    BALANCE_TOLERANCE,
    amounts_are_balanced,
)

S = StagingAccountingEntry


def staging_voucher_group_key_expr():
    """与 staging_review_service.voucher_group_key 一致的 SQL 表达式。"""
    date_text = func.coalesce(cast(S.voucher_date, String), "")
    voucher_group = func.concat(S.voucher_no, literal("|"), date_text)
    orphan_group = func.concat(literal("__row_"), cast(S.id, String))
    return case(
        (and_(S.voucher_no.isnot(None), S.voucher_no != ""), voucher_group),
        else_=orphan_group,
    )


def _build_voucher_groups_subquery(db: Session, job_id: int):
    group_key = staging_voucher_group_key_expr().label("group_key")
    verified_line = case(
        (S.review_status.in_(tuple(VERIFIED_REVIEW_STATUSES)), 1),
        else_=0,
    )
    return (
        db.query(
            group_key,
            func.max(S.voucher_no).label("voucher_no"),
            func.max(S.voucher_date).label("voucher_date"),
            func.count().label("line_count"),
            func.sum(S.debit_amount).label("debit_total"),
            func.sum(S.credit_amount).label("credit_total"),
            func.sum(verified_line).label("verified_count"),
            func.min(S.entry_line_no).label("min_entry_line_no"),
            func.min(S.id).label("min_row_id"),
            func.max(cast(S.spot_check_flag, Integer)).label("spot_check_flag"),
        )
        .filter(S.import_job_id == job_id)
        .group_by(group_key)
        .subquery("staging_voucher_groups")
    )


def _build_voucher_anchor_subquery(job_id: int):
    group_key = staging_voucher_group_key_expr().label("group_key")
    ranked = (
        select(
            group_key,
            S.id.label("anchor_entry_id"),
            S.summary,
            S.account_name,
            S.source_preparer_name,
            S.cross_reviewed_by_user_id,
            S.cross_reviewed_at,
            S.compliance_hint,
            S.compliance_severity,
            func.row_number()
            .over(
                partition_by=group_key,
                order_by=(S.entry_line_no.asc(), S.id.asc()),
            )
            .label("rn"),
        )
        .where(S.import_job_id == job_id)
        .subquery("staging_voucher_ranked")
    )
    return (
        select(ranked)
        .where(ranked.c.rn == 1)
        .subquery("staging_voucher_anchor")
    )


def _voucher_balance_delta_sql(debit_col, credit_col):
    """SQLite 对 SUM 列做 != 比较可能误报，改用 abs 差额。"""
    return func.abs(debit_col - credit_col)


def _voucher_is_balanced_sql(debit_col, credit_col):
    return _voucher_balance_delta_sql(debit_col, credit_col) <= BALANCE_TOLERANCE


def _aggregate_review_status(verified_count, line_count):
    return case(
        (verified_count == line_count, literal("verified")),
        (verified_count > 0, literal("partial")),
        else_=literal("draft"),
    )


def _voucher_display_label(voucher_no: str | None, min_row_id: int | None) -> str:
    if voucher_no:
        return voucher_no
    return f"分录#{min_row_id or 0}"


def _stats_from_groups_subquery(db: Session, job_id: int, groups) -> dict[str, Any]:
    g = groups.c

    total_vouchers = db.query(func.count()).select_from(groups).scalar() or 0
    verified_vouchers = (
        db.query(func.count())
        .select_from(groups)
        .filter(g.verified_count == g.line_count)
        .scalar()
        or 0
    )
    partial_vouchers = (
        db.query(func.count())
        .select_from(groups)
        .filter(g.verified_count > 0, g.verified_count < g.line_count)
        .scalar()
        or 0
    )
    unbalanced_rows = (
        db.query(g.voucher_no, g.min_row_id)
        .select_from(groups)
        .filter(_voucher_balance_delta_sql(g.debit_total, g.credit_total) > BALANCE_TOLERANCE)
        .all()
    )
    unbalanced_voucher_nos: list[str] = []
    seen_unbalanced: set[str] = set()
    for voucher_no, min_row_id in unbalanced_rows:
        label = _voucher_display_label(voucher_no, min_row_id)
        if label in seen_unbalanced:
            continue
        seen_unbalanced.add(label)
        unbalanced_voucher_nos.append(label)
    total_lines = (
        db.query(func.count())
        .select_from(S)
        .filter(S.import_job_id == job_id)
        .scalar()
        or 0
    )
    anchor = _build_voucher_anchor_subquery(job_id)
    a = anchor.c
    spot_check_vouchers = (
        db.query(func.count())
        .select_from(groups)
        .filter(g.spot_check_flag > 0)
        .scalar()
        or 0
    )
    compliance_reviewed_vouchers = (
        db.query(func.count())
        .select_from(groups)
        .join(anchor, g.group_key == a.group_key)
        .filter(a.compliance_hint.isnot(None), a.compliance_hint != "")
        .scalar()
        or 0
    )
    compliance_pending_vouchers = (
        db.query(func.count())
        .select_from(groups)
        .join(anchor, g.group_key == a.group_key)
        .filter(
            g.spot_check_flag > 0,
            or_(a.compliance_hint.is_(None), a.compliance_hint == ""),
        )
        .scalar()
        or 0
    )
    return {
        "total_vouchers": int(total_vouchers),
        "verified_vouchers": int(verified_vouchers),
        "partial_vouchers": int(partial_vouchers),
        "unbalanced_voucher_nos": unbalanced_voucher_nos,
        "total_lines": int(total_lines),
        "spot_check_vouchers": int(spot_check_vouchers),
        "compliance_pending_vouchers": int(compliance_pending_vouchers),
        "compliance_reviewed_vouchers": int(compliance_reviewed_vouchers),
    }


def compute_review_stats_sql(db: Session, job_id: int) -> dict[str, Any]:
    groups = _build_voucher_groups_subquery(db, job_id)
    return _stats_from_groups_subquery(db, job_id, groups)


def _apply_voucher_filters(query, groups, anchor, *, review_filter: str, search: str | None):
    g = groups.c
    a = anchor.c
    review_status = _aggregate_review_status(g.verified_count, g.line_count)
    is_balanced = _voucher_is_balanced_sql(g.debit_total, g.credit_total)

    if review_filter == "pending":
        query = query.filter(review_status != literal("verified"))
    elif review_filter == "verified":
        query = query.filter(review_status == literal("verified"))
    elif review_filter == "unbalanced":
        query = query.filter(~is_balanced)
    elif review_filter == "spot_check":
        query = query.filter(g.spot_check_flag > 0)
    elif review_filter == "compliance_pending":
        query = query.filter(
            g.spot_check_flag > 0,
            or_(a.compliance_hint.is_(None), a.compliance_hint == ""),
        )
    elif review_filter == "compliance_reviewed":
        query = query.filter(a.compliance_hint.isnot(None), a.compliance_hint != "")

    if search:
        needle = f"%{search.strip().lower()}%"
        orphan_label = func.concat(literal("分录#"), cast(g.min_row_id, String))
        query = query.filter(
            or_(
                func.lower(func.coalesce(g.voucher_no, "")).like(needle),
                func.lower(func.coalesce(a.summary, "")).like(needle),
                func.lower(func.coalesce(a.account_name, "")).like(needle),
                func.lower(orphan_label).like(needle),
            )
        )
    return query


def _summary_from_row(row: Any) -> dict[str, Any]:
    g = row
    verified_count = int(g.verified_count or 0)
    line_count = int(g.line_count or 0)
    if verified_count == line_count:
        review_status = "verified"
    elif verified_count > 0:
        review_status = "partial"
    else:
        review_status = "draft"

    debit_total = g.debit_total or Decimal("0")
    credit_total = g.credit_total or Decimal("0")
    voucher_no = g.voucher_no
    voucher_word = None
    if voucher_no and "-" in voucher_no:
        voucher_word = voucher_no.split("-", 1)[0]

    cross_reviewed_at = g.cross_reviewed_at
    if isinstance(cross_reviewed_at, datetime):
        cross_reviewed_at = cross_reviewed_at.isoformat()

    voucher_date = g.voucher_date
    if isinstance(voucher_date, date):
        voucher_date = voucher_date.isoformat()

    summary_preview = (g.summary or "")[:120] or None
    return {
        "group_key": g.group_key,
        "voucher_no": voucher_no,
        "voucher_date": voucher_date,
        "voucher_word": voucher_word,
        "line_count": line_count,
        "debit_total": float(debit_total),
        "credit_total": float(credit_total),
        "is_balanced": amounts_are_balanced(debit_total, credit_total),
        "review_status": review_status,
        "source_preparer_name": g.source_preparer_name,
        "cross_reviewed_by_user_id": g.cross_reviewed_by_user_id,
        "cross_reviewed_at": cross_reviewed_at,
        "compliance_hint": g.compliance_hint,
        "compliance_severity": g.compliance_severity or "info",
        "spot_check_flag": bool(g.spot_check_flag),
        "summary_preview": summary_preview,
        "anchor_entry_id": int(g.anchor_entry_id),
    }


def paginate_preview_vouchers_sql(
    db: Session,
    job_id: int,
    *,
    review_filter: str = "all",
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
    groups=None,
) -> tuple[list[dict[str, Any]], int]:
    if groups is None:
        groups = _build_voucher_groups_subquery(db, job_id)
    anchor = _build_voucher_anchor_subquery(job_id)
    g = groups.c
    a = anchor.c

    base = (
        db.query(
            g.group_key,
            g.voucher_no,
            g.voucher_date,
            g.line_count,
            g.debit_total,
            g.credit_total,
            g.verified_count,
            g.min_entry_line_no,
            g.spot_check_flag,
            a.anchor_entry_id,
            a.summary,
            a.account_name,
            a.source_preparer_name,
            a.cross_reviewed_by_user_id,
            a.cross_reviewed_at,
            a.compliance_hint,
            a.compliance_severity,
        )
        .select_from(groups)
        .join(anchor, g.group_key == a.group_key)
    )
    filtered = _apply_voucher_filters(
        base,
        groups,
        anchor,
        review_filter=review_filter,
        search=search,
    )

    total = db.query(func.count()).select_from(filtered.subquery("filtered_voucher_groups")).scalar() or 0
    rows = (
        filtered.order_by(
            g.voucher_date.asc().nullsfirst(),
            g.voucher_no.asc().nullsfirst(),
            g.min_entry_line_no.asc(),
            g.group_key.asc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_summary_from_row(row) for row in rows], int(total)
