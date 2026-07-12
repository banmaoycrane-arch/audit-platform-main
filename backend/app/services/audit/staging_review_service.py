"""Staging 草稿按整张凭证复核与确认前校验。"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session, load_only

from app.db.models import StagingAccountingEntry

# 凭证复核列表/统计仅需列，避免加载 entry_tags_payload 等大 JSON 字段。
_STAGING_VOUCHER_REVIEW_LOAD_ONLY = (
    StagingAccountingEntry.id,
    StagingAccountingEntry.import_job_id,
    StagingAccountingEntry.voucher_no,
    StagingAccountingEntry.voucher_date,
    StagingAccountingEntry.entry_line_no,
    StagingAccountingEntry.debit_amount,
    StagingAccountingEntry.credit_amount,
    StagingAccountingEntry.review_status,
    StagingAccountingEntry.summary,
    StagingAccountingEntry.account_name,
    StagingAccountingEntry.compliance_hint,
    StagingAccountingEntry.compliance_severity,
    StagingAccountingEntry.spot_check_flag,
    StagingAccountingEntry.source_preparer_name,
    StagingAccountingEntry.cross_reviewed_by_user_id,
    StagingAccountingEntry.cross_reviewed_at,
)


def load_staging_rows_for_voucher_review(db: Session, job_id: int) -> list[StagingAccountingEntry]:
    """加载 staging 行（凭证复核用轻量列集）。"""
    return (
        db.query(StagingAccountingEntry)
        .options(load_only(*_STAGING_VOUCHER_REVIEW_LOAD_ONLY))
        .filter(StagingAccountingEntry.import_job_id == job_id)
        .order_by(
            StagingAccountingEntry.voucher_no,
            StagingAccountingEntry.entry_line_no,
        )
        .all()
    )


def query_staging_rows_by_group_key(
    db: Session,
    job_id: int,
    group_key: str,
) -> list[StagingAccountingEntry]:
    """按 group_key 查询单张凭证分录，避免为打开抽屉而扫描全量 staging。"""
    if group_key.startswith("__row_"):
        row_id = int(group_key.removeprefix("__row_"))
        row = (
            db.query(StagingAccountingEntry)
            .filter(
                StagingAccountingEntry.import_job_id == job_id,
                StagingAccountingEntry.id == row_id,
            )
            .first()
        )
        return [row] if row else []

    parts = group_key.split("|", 1)
    voucher_no = parts[0]
    query = db.query(StagingAccountingEntry).filter(
        StagingAccountingEntry.import_job_id == job_id,
        StagingAccountingEntry.voucher_no == voucher_no,
    )
    if len(parts) > 1 and parts[1]:
        query = query.filter(StagingAccountingEntry.voucher_date == date.fromisoformat(parts[1]))
    return query.order_by(StagingAccountingEntry.entry_line_no).all()

VERIFIED_REVIEW_STATUSES = frozenset({"verified", "ready"})

# 借贷平衡容差（元）。SQLite 对 SUM 结果直接 != 比较可能误报，统一用差额容差。
BALANCE_TOLERANCE = Decimal("0.01")


def voucher_balance_delta(total_debit: Decimal, total_credit: Decimal) -> Decimal:
    return abs(total_debit - total_credit)


def amounts_are_balanced(total_debit: Decimal, total_credit: Decimal) -> bool:
    return voucher_balance_delta(total_debit, total_credit) <= BALANCE_TOLERANCE


def voucher_group_key(row: StagingAccountingEntry) -> str:
    if row.voucher_no:
        date_part = row.voucher_date.isoformat() if row.voucher_date else ""
        return f"{row.voucher_no}|{date_part}"
    return f"__row_{row.id}"


def voucher_display_label(group: list[StagingAccountingEntry]) -> str:
    first = group[0]
    if first.voucher_no:
        return first.voucher_no
    return f"分录#{first.id}"


def group_staging_rows(rows: list[StagingAccountingEntry]) -> dict[str, list[StagingAccountingEntry]]:
    groups: dict[str, list[StagingAccountingEntry]] = {}
    for row in rows:
        groups.setdefault(voucher_group_key(row), []).append(row)
    return groups


def is_voucher_balanced(rows: list[StagingAccountingEntry]) -> bool:
    total_debit = sum((row.debit_amount or Decimal("0")) for row in rows)
    total_credit = sum((row.credit_amount or Decimal("0")) for row in rows)
    return amounts_are_balanced(total_debit, total_credit)


def is_voucher_fully_verified(rows: list[StagingAccountingEntry]) -> bool:
    return all(row.review_status in VERIFIED_REVIEW_STATUSES for row in rows)


def compute_review_stats(rows: list[StagingAccountingEntry]) -> dict[str, Any]:
    groups = group_staging_rows(rows)
    verified_vouchers = 0
    partial_vouchers = 0
    unbalanced_voucher_nos: list[str] = []

    for group in groups.values():
        verified_line_count = sum(
            1 for row in group if row.review_status in VERIFIED_REVIEW_STATUSES
        )
        if verified_line_count == len(group):
            verified_vouchers += 1
        elif verified_line_count > 0:
            partial_vouchers += 1
        if not is_voucher_balanced(group):
            label = voucher_display_label(group)
            if label not in unbalanced_voucher_nos:
                unbalanced_voucher_nos.append(label)

    return {
        "total_vouchers": len(groups),
        "verified_vouchers": verified_vouchers,
        "partial_vouchers": partial_vouchers,
        "unbalanced_voucher_nos": unbalanced_voucher_nos,
        "total_lines": len(rows),
    }


def validate_staging_ready_for_confirm(rows: list[StagingAccountingEntry]) -> str | None:
    if not rows:
        return "没有可确认的草稿分录，请先上传并解析文件"

    groups = group_staging_rows(rows)
    for group in groups.values():
        label = voucher_display_label(group)
        if not is_voucher_balanced(group):
            return f"凭证「{label}」借贷不平衡，请修正后再确认入账"
        verified_line_count = sum(
            1 for row in group if row.review_status in VERIFIED_REVIEW_STATUSES
        )
        if verified_line_count != len(group):
            if verified_line_count > 0:
                return f"凭证「{label}」存在部分复核的分录，请按整张凭证统一复核后再确认入账"
            return f"尚有凭证未完成复核，请按整张凭证复核后再确认入账"
    return None


def rows_in_same_voucher(
    db: Session,
    anchor: StagingAccountingEntry,
) -> list[StagingAccountingEntry]:
    query = db.query(StagingAccountingEntry).filter(
        StagingAccountingEntry.import_job_id == anchor.import_job_id,
    )
    if anchor.voucher_no:
        query = query.filter(StagingAccountingEntry.voucher_no == anchor.voucher_no)
        if anchor.voucher_date is not None:
            query = query.filter(StagingAccountingEntry.voucher_date == anchor.voucher_date)
        return query.order_by(StagingAccountingEntry.entry_line_no).all()
    return [anchor]


def apply_voucher_review_status(
    db: Session,
    anchor: StagingAccountingEntry,
    review_status: str,
    *,
    reviewed_by_user_id: int | None = None,
) -> list[StagingAccountingEntry]:
    rows = rows_in_same_voucher(db, anchor)
    now = datetime.now(timezone.utc)
    for row in rows:
        row.review_status = review_status
        if review_status in VERIFIED_REVIEW_STATUSES and reviewed_by_user_id is not None:
            row.cross_reviewed_by_user_id = reviewed_by_user_id
            row.cross_reviewed_at = now
        elif review_status == "draft":
            row.cross_reviewed_by_user_id = None
            row.cross_reviewed_at = None
    return rows


def assert_voucher_editable(rows: list[StagingAccountingEntry]) -> None:
    if any(row.review_status in VERIFIED_REVIEW_STATUSES for row in rows):
        label = voucher_display_label(rows)
        raise ValueError(f"凭证「{label}」已复核，请先取消整张凭证复核后再修改分录")


def aggregate_voucher_review_status(rows: list[StagingAccountingEntry]) -> str:
    verified_count = sum(1 for row in rows if row.review_status in VERIFIED_REVIEW_STATUSES)
    if verified_count == len(rows):
        return "verified"
    if verified_count > 0:
        return "partial"
    return "draft"


def summarize_preview_vouchers(
    rows: list[StagingAccountingEntry],
    *,
    review_filter: str = "all",
    search: str | None = None,
) -> list[dict[str, Any]]:
    groups = group_staging_rows(rows)
    summaries: list[dict[str, Any]] = []

    def sort_key(item: tuple[str, list[StagingAccountingEntry]]) -> tuple:
        group = item[1]
        first = group[0]
        return (
            first.voucher_date.isoformat() if first.voucher_date else "",
            first.voucher_no or "",
            first.entry_line_no or 0,
        )

    for key, group in sorted(groups.items(), key=sort_key):
        group = sorted(group, key=lambda row: row.entry_line_no or 0)
        first = group[0]
        review_status = aggregate_voucher_review_status(group)
        balanced = is_voucher_balanced(group)

        if review_filter == "pending" and review_status == "verified":
            continue
        if review_filter == "verified" and review_status != "verified":
            continue
        if review_filter == "unbalanced" and balanced:
            continue

        label = voucher_display_label(group)
        if search:
            needle = search.strip().lower()
            haystacks = [
                label.lower(),
                (first.summary or "").lower(),
                (first.account_name or "").lower(),
            ]
            if not any(needle in text for text in haystacks if text):
                continue

        debit_total = sum((row.debit_amount or Decimal("0")) for row in group)
        credit_total = sum((row.credit_amount or Decimal("0")) for row in group)
        compliance_hints = [row.compliance_hint for row in group if row.compliance_hint]
        severities = [row.compliance_severity or "info" for row in group if row.compliance_hint]
        severity_rank = {"info": 0, "warning": 1, "error": 2}
        top_severity = max(severities, key=lambda item: severity_rank.get(item, 0)) if severities else "info"

        voucher_word = None
        if first.voucher_no and "-" in first.voucher_no:
            voucher_word = first.voucher_no.split("-", 1)[0]

        summaries.append(
            {
                "group_key": key,
                "voucher_no": first.voucher_no,
                "voucher_date": first.voucher_date.isoformat() if first.voucher_date else None,
                "voucher_word": voucher_word,
                "line_count": len(group),
                "debit_total": float(debit_total),
                "credit_total": float(credit_total),
                "is_balanced": balanced,
                "review_status": review_status,
                "source_preparer_name": first.source_preparer_name,
                "cross_reviewed_by_user_id": first.cross_reviewed_by_user_id,
                "cross_reviewed_at": (
                    first.cross_reviewed_at.isoformat() if first.cross_reviewed_at else None
                ),
                "compliance_hint": compliance_hints[0] if compliance_hints else None,
                "compliance_severity": top_severity,
                "spot_check_flag": any(row.spot_check_flag for row in group),
                "summary_preview": (first.summary or "")[:120] or None,
                "anchor_entry_id": first.id,
            }
        )
    return summaries


def staging_rows_for_group_key(
    rows: list[StagingAccountingEntry],
    group_key: str,
) -> list[StagingAccountingEntry]:
    groups = group_staging_rows(rows)
    group = groups.get(group_key, [])
    return sorted(group, key=lambda row: row.entry_line_no or 0)

