"""从导入分录中识别会计期间（月份）。"""

from __future__ import annotations

from calendar import monthrange
from collections import Counter
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AccountingEntry, AccountingPeriod


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()[:10]
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    return None


def detect_dominant_month(voucher_dates: list[Any]) -> date | None:
    """从凭证日期列表中识别出现次数最多的月份，返回该月第一天。"""
    month_counter: Counter[tuple[int, int]] = Counter()
    for raw in voucher_dates:
        parsed = _coerce_date(raw)
        if parsed is None:
            continue
        month_counter[(parsed.year, parsed.month)] += 1

    if not month_counter:
        return None

    year, month = month_counter.most_common(1)[0][0]
    return date(year, month, 1)


def build_month_period_suggestion(target_month: date) -> dict[str, str]:
    """根据目标月份生成月度期间建议。"""
    last_day = monthrange(target_month.year, target_month.month)[1]
    return {
        "period_code": f"{target_month.year}-{target_month.month:02d}",
        "period_type": "monthly",
        "start_date": date(target_month.year, target_month.month, 1).isoformat(),
        "end_date": date(target_month.year, target_month.month, last_day).isoformat(),
        "detected_from": "voucher_dates",
        "dominant_month": f"{target_month.year}-{target_month.month:02d}",
    }


def suggest_period_for_job(db: Session, job_id: int, organization_id: int | None = None) -> dict[str, Any]:
    """基于任务分录凭证日期推荐会计期间。"""
    entries = db.query(AccountingEntry).filter(AccountingEntry.import_job_id == job_id).all()
    voucher_dates = [entry.voucher_date for entry in entries]
    dominant_month = detect_dominant_month(voucher_dates)

    if dominant_month is None:
        return {
            "detected_month": None,
            "suggested_period": None,
            "matched_period": None,
            "reason": "分录中未识别到有效凭证日期，请手工选择会计期间",
        }

    suggested = build_month_period_suggestion(dominant_month)
    matched_period = None
    reason = f"系统根据序时簿凭证日期识别主要月份为 {suggested['dominant_month']}，建议使用该月度期间"

    if organization_id:
        matched = (
            db.query(AccountingPeriod)
            .filter(
                AccountingPeriod.organization_id == organization_id,
                AccountingPeriod.start_date <= dominant_month,
                AccountingPeriod.end_date >= dominant_month,
                AccountingPeriod.status.in_(["open", "reopened"]),
            )
            .order_by(AccountingPeriod.start_date.desc(), AccountingPeriod.id.desc())
            .first()
        )
        if matched:
            matched_period = {
                "id": matched.id,
                "period_code": matched.period_code,
                "period_type": matched.period_type,
                "start_date": matched.start_date.isoformat(),
                "end_date": matched.end_date.isoformat(),
                "status": matched.status,
            }
            reason = (
                f"序时簿凭证日期主要落在 {suggested['dominant_month']}，"
                f"已匹配到 open/reopened 期间 {matched.period_code}"
            )

    return {
        "detected_month": suggested["dominant_month"],
        "suggested_period": suggested,
        "matched_period": matched_period,
        "reason": reason,
    }
