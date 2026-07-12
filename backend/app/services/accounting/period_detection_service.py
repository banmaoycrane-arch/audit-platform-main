"""从导入分录中识别会计期间（月份）。"""

from __future__ import annotations

from calendar import monthrange
from collections import Counter
from datetime import date
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import AccountingEntry, AccountingPeriod, ImportJob, StagingAccountingEntry, Voucher


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


def detect_distinct_months(voucher_dates: list[Any]) -> list[date]:
    """从凭证日期列表中识别所有不重复月份，返回各月第一天（升序）。"""
    month_keys: set[tuple[int, int]] = set()
    for raw in voucher_dates:
        parsed = _coerce_date(raw)
        if parsed is None:
            continue
        month_keys.add((parsed.year, parsed.month))
    return sorted(date(year, month, 1) for year, month in month_keys)


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


def _month_code(value: date) -> str:
    return f"{value.year}-{value.month:02d}"


def _collect_voucher_dates_for_job(db: Session, job_id: int) -> tuple[str, list[Any], list[Voucher]]:
    """读取任务关联的凭证日期：优先正式凭证，其次 staging 草稿，最后历史分录。"""
    vouchers = db.query(Voucher).filter(Voucher.import_job_id == job_id).all()
    if vouchers:
        return "vouchers", [voucher.voucher_date for voucher in vouchers if voucher.voucher_date], vouchers

    staging_rows = (
        db.query(StagingAccountingEntry)
        .filter(StagingAccountingEntry.import_job_id == job_id)
        .all()
    )
    if staging_rows:
        return (
            "staging",
            [row.voucher_date for row in staging_rows if row.voucher_date],
            [],
        )

    entries = db.query(AccountingEntry).filter(AccountingEntry.import_job_id == job_id).all()
    if entries:
        return "entries", [entry.voucher_date for entry in entries if entry.voucher_date], []

    raise ValueError("导入任务尚无凭证或分录，请先完成文件解析")


def _distinct_staging_voucher_count(db: Session, job_id: int) -> int:
    rows = (
        db.query(StagingAccountingEntry)
        .filter(StagingAccountingEntry.import_job_id == job_id)
        .all()
    )
    groups: set[str] = set()
    for idx, row in enumerate(rows):
        groups.add(row.voucher_no or f"__no_voucher__:{idx}")
    return len(groups)


def _save_period_mapping(job: ImportJob, mapping: dict[str, Any]) -> None:
    draft_data = dict(job.draft_data or {})
    draft_data["period_mapping"] = mapping
    job.draft_data = draft_data
    flag_modified(job, "draft_data")


def get_period_mapping_for_job(job: ImportJob) -> dict[str, Any]:
    draft_data = job.draft_data or {}
    mapping = draft_data.get("period_mapping")
    return mapping if isinstance(mapping, dict) else {}


def resolve_voucher_period_id(job: ImportJob, voucher_date: date | None) -> int | None:
    """根据已保存的期间映射配置，为确认入账时的凭证解析 period_id。"""
    mapping = get_period_mapping_for_job(job)
    if not mapping:
        return job.audit_period_id

    mode = mapping.get("period_mapping_mode")
    if mode == "unify_target":
        if mapping.get("period_mode") == "fixed":
            primary = mapping.get("primary_period_id")
            return int(primary) if primary is not None else job.audit_period_id
        if mapping.get("period_mode") == "adaptive" and voucher_date is not None:
            month_period_ids = mapping.get("month_period_ids") or {}
            return month_period_ids.get(_month_code(voucher_date))
    if mode == "preserve_source" and voucher_date is not None:
        month_period_ids = mapping.get("month_period_ids") or {}
        return month_period_ids.get(_month_code(voucher_date))
    return job.audit_period_id


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
    """基于任务分录/草稿凭证日期推荐会计期间。"""
    try:
        _, voucher_dates, _ = _collect_voucher_dates_for_job(db, job_id)
    except ValueError:
        return {
            "detected_month": None,
            "detected_months": [],
            "is_multi_period": False,
            "suggested_period": None,
            "matched_period": None,
            "reason": "分录中未识别到有效凭证日期，请手工选择会计期间",
        }

    distinct_months = detect_distinct_months(voucher_dates)
    dominant_month = detect_dominant_month(voucher_dates)

    if dominant_month is None:
        return {
            "detected_month": None,
            "detected_months": [],
            "is_multi_period": False,
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

    detected_month_codes = [f"{m.year}-{m.month:02d}" for m in distinct_months]
    is_multi_period = len(distinct_months) > 1
    if is_multi_period:
        reason = (
            f"序时簿凭证日期跨越 {len(distinct_months)} 个月份（{', '.join(detected_month_codes)}）。"
            "请选择「与原始文件一致」保留各凭证原期间，或「导入后统一期间」指定目标期间。"
        )

    return {
        "detected_month": suggested["dominant_month"],
        "detected_months": detected_month_codes,
        "is_multi_period": is_multi_period,
        "suggested_period": suggested,
        "matched_period": matched_period,
        "reason": reason,
    }


def _filter_periods_for_job(db: Session, job: ImportJob) -> list[AccountingPeriod]:
    query = db.query(AccountingPeriod).filter(AccountingPeriod.organization_id == job.organization_id)
    if job.ledger_id is not None:
        query = query.filter(
            (AccountingPeriod.ledger_id == job.ledger_id) | (AccountingPeriod.ledger_id.is_(None))
        )
    return query.order_by(AccountingPeriod.start_date.asc()).all()


def _find_period_for_date(periods: list[AccountingPeriod], voucher_date: date) -> AccountingPeriod | None:
    return next(
        (period for period in periods if period.start_date <= voucher_date <= period.end_date),
        None,
    )


def _create_month_period(db: Session, job: ImportJob, month_start: date) -> AccountingPeriod:
    suggestion = build_month_period_suggestion(month_start)
    period = AccountingPeriod(
        organization_id=job.organization_id,
        ledger_id=job.ledger_id,
        period_code=suggestion["period_code"],
        period_type="monthly",
        start_date=date.fromisoformat(suggestion["start_date"]),
        end_date=date.fromisoformat(suggestion["end_date"]),
        status="open",
    )
    db.add(period)
    db.flush()
    return period


def _ensure_periods_for_months(
    db: Session,
    job: ImportJob,
    month_starts: list[date],
    existing_periods: list[AccountingPeriod],
) -> dict[tuple[int, int], AccountingPeriod]:
    """为指定月份列表匹配或创建会计期间，返回 (year, month) -> period 映射。"""
    period_map: dict[tuple[int, int], AccountingPeriod] = {}
    periods = list(existing_periods)

    for month_start in month_starts:
        key = (month_start.year, month_start.month)
        if key in period_map:
            continue
        matched = _find_period_for_date(periods, month_start)
        if matched:
            period_map[key] = matched
            continue
        created = _create_month_period(db, job, month_start)
        periods.append(created)
        period_map[key] = created

    return period_map


def _batch_create_periods_in_range(
    db: Session,
    job: ImportJob,
    start_date: date,
    end_date: date,
) -> list[AccountingPeriod]:
    """在指定日期范围内按自然月创建缺失期间（与已有期间重叠则跳过）。"""
    existing_periods = _filter_periods_for_job(db, job)
    month_starts: list[date] = []
    current_year, current_month = start_date.year, start_date.month
    end_year, end_month = end_date.year, end_date.month

    while (current_year, current_month) <= (end_year, end_month):
        month_starts.append(date(current_year, current_month, 1))
        if current_month == 12:
            current_year += 1
            current_month = 1
        else:
            current_month += 1

    _ensure_periods_for_months(db, job, month_starts, existing_periods)
    db.flush()
    return _filter_periods_for_job(db, job)


def apply_import_period_mapping(
    db: Session,
    job: ImportJob,
    *,
    period_mapping_mode: str,
    period_mode: str | None = None,
    period_id: int | None = None,
    period_start_date: date | None = None,
    period_end_date: date | None = None,
) -> dict[str, Any]:
    """
    为结构化导入任务分配会计期间。

    preserve_source: 按凭证日期自动匹配/创建各月期间，一凭证一期间。
    unify_target + fixed: 全部凭证归入指定单一期间。
    unify_target + adaptive: 在指定范围内按凭证日期匹配期间。

    预览阶段（staging 草稿）仅写入 job.draft_data.period_mapping，确认入账时再落到凭证。
    """
    source_kind, voucher_dates, vouchers = _collect_voucher_dates_for_job(db, job.id)

    assigned_count = 0
    created_period_codes: list[str] = []
    used_period_codes: set[str] = set()
    out_of_range_count = 0
    month_period_ids: dict[str, int] = {}
    mapping_payload: dict[str, Any] = {
        "period_mapping_mode": period_mapping_mode,
        "period_mode": period_mode,
        "primary_period_id": None,
        "period_start_date": period_start_date.isoformat() if period_start_date else None,
        "period_end_date": period_end_date.isoformat() if period_end_date else None,
        "month_period_ids": month_period_ids,
    }

    if period_mapping_mode == "preserve_source":
        distinct_months = detect_distinct_months(voucher_dates)
        if not distinct_months:
            raise ValueError("无法从凭证日期识别有效月份，请检查序时簿日期列")
        existing_periods = _filter_periods_for_job(db, job)
        existing_codes = {p.period_code for p in existing_periods}
        period_map = _ensure_periods_for_months(db, job, distinct_months, existing_periods)
        created_period_codes = sorted(
            {p.period_code for p in period_map.values() if p.period_code not in existing_codes}
        )
        for (year, month), period in period_map.items():
            month_period_ids[f"{year}-{month:02d}"] = period.id
            used_period_codes.add(period.period_code)

        if source_kind == "vouchers":
            for voucher in vouchers:
                if not voucher.voucher_date:
                    continue
                key = (voucher.voucher_date.year, voucher.voucher_date.month)
                period = period_map.get(key)
                if period:
                    voucher.period_id = period.id
                    assigned_count += 1
        else:
            staging_rows = (
                db.query(StagingAccountingEntry)
                .filter(StagingAccountingEntry.import_job_id == job.id)
                .all()
            )
            grouped: set[str] = set()
            for idx, row in enumerate(staging_rows):
                voucher_key = row.voucher_no or f"__no_voucher__:{idx}"
                if voucher_key in grouped:
                    continue
                if not row.voucher_date:
                    continue
                key = (row.voucher_date.year, row.voucher_date.month)
                if key in period_map:
                    grouped.add(voucher_key)
                    assigned_count += 1
    elif period_mapping_mode == "unify_target":
        if period_mode == "fixed":
            if not period_id:
                raise ValueError("统一期间模式下请选择目标会计期间")
            period = db.get(AccountingPeriod, period_id)
            if not period:
                raise ValueError("指定的会计期间不存在")
            mapping_payload["primary_period_id"] = period.id
            if source_kind == "vouchers":
                for voucher in vouchers:
                    voucher.period_id = period.id
                    assigned_count += 1
            else:
                assigned_count = _distinct_staging_voucher_count(db, job.id)
            used_period_codes.add(period.period_code)
        elif period_mode == "adaptive":
            if not period_start_date or not period_end_date:
                raise ValueError("自适应统一期间模式下请指定期间范围起止日期")
            if period_start_date > period_end_date:
                raise ValueError("期间范围开始日期不能晚于结束日期")
            periods = _batch_create_periods_in_range(db, job, period_start_date, period_end_date)
            for period in periods:
                if period.start_date >= period_start_date and period.end_date <= period_end_date:
                    month_period_ids[_month_code(period.start_date)] = period.id
                    used_period_codes.add(period.period_code)

            if source_kind == "vouchers":
                for voucher in vouchers:
                    if not voucher.voucher_date:
                        continue
                    if voucher.voucher_date < period_start_date or voucher.voucher_date > period_end_date:
                        out_of_range_count += 1
                        continue
                    matched = _find_period_for_date(periods, voucher.voucher_date)
                    if matched:
                        voucher.period_id = matched.id
                        month_period_ids[_month_code(voucher.voucher_date)] = matched.id
                        used_period_codes.add(matched.period_code)
                        assigned_count += 1
            else:
                staging_rows = (
                    db.query(StagingAccountingEntry)
                    .filter(StagingAccountingEntry.import_job_id == job.id)
                    .all()
                )
                grouped: set[str] = set()
                for idx, row in enumerate(staging_rows):
                    voucher_key = row.voucher_no or f"__no_voucher__:{idx}"
                    if voucher_key in grouped or not row.voucher_date:
                        continue
                    if row.voucher_date < period_start_date or row.voucher_date > period_end_date:
                        out_of_range_count += 1
                        continue
                    matched = _find_period_for_date(periods, row.voucher_date)
                    if matched:
                        grouped.add(voucher_key)
                        month_period_ids[_month_code(row.voucher_date)] = matched.id
                        used_period_codes.add(matched.period_code)
                        assigned_count += 1
        else:
            raise ValueError("统一期间模式下请选择 adaptive 或 fixed 子模式")
    else:
        raise ValueError(f"不支持的期间映射模式: {period_mapping_mode}")

    mapping_payload["month_period_ids"] = month_period_ids
    mapping_payload["created_period_codes"] = sorted(set(created_period_codes))
    mapping_payload["used_period_codes"] = sorted(used_period_codes)
    _save_period_mapping(job, mapping_payload)

    db.commit()
    total_voucher_count = len(vouchers) if vouchers else _distinct_staging_voucher_count(db, job.id)
    return {
        "period_mapping_mode": period_mapping_mode,
        "period_mode": period_mode,
        "assigned_voucher_count": assigned_count,
        "total_voucher_count": total_voucher_count,
        "created_period_codes": sorted(set(created_period_codes)),
        "used_period_codes": sorted(used_period_codes),
        "out_of_range_count": out_of_range_count,
        "primary_period_id": period_id if period_mode == "fixed" else None,
        "staging_only": source_kind == "staging",
    }
