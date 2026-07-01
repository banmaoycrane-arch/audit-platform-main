from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
import time
from urllib import request as urllib_request

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import AccountingEntry, AccountingPeriod, ImportJob, Organization, SourceFile
from app.db.session import get_db
from app.services import entry_generation_service, lifecycle_service
from app.services.audit_day_book_service import process_day_book_import
from app.services.import_routing_service import is_day_book_source_type

router = APIRouter(prefix="/api/import-jobs", tags=["entry-generation"])


#region debug-point generate-entries-runtime
def _debug_report_generate_entries(event: str, payload: dict) -> None:
    try:
        data = json.dumps(
            {
                "sessionId": "sequence-import-parser",
                "runId": "pre",
                "hypothesisId": "generate-entries-runtime",
                "event": event,
                "payload": payload,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        req = urllib_request.Request(
            "http://127.0.0.1:7777/event",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib_request.urlopen(req, timeout=0.2).read()
    except Exception:
        pass
#endregion


#region debug-point daybook-step3-performance
def _debug_report_daybook_step3_performance(event: str, payload: dict) -> None:
    try:
        data = json.dumps(
            {
                "sessionId": "daybook-step3-performance",
                "runId": "pre",
                "hypothesisId": "step3-payload-size",
                "event": event,
                "payload": payload,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        req = urllib_request.Request(
            "http://127.0.0.1:7777/event",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib_request.urlopen(req, timeout=0.2).read()
    except Exception:
        pass
#endregion


#region debug-point auto-period-step3
def _debug_report_auto_period_step3(event: str, payload: dict) -> None:
    try:
        data = json.dumps(
            {
                "sessionId": "auto-period-step3",
                "runId": "pre",
                "hypothesisId": "period-autodetect",
                "event": event,
                "payload": payload,
            },
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
        req = urllib_request.Request(
            "http://127.0.0.1:7777/event",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib_request.urlopen(req, timeout=0.2).read()
    except Exception:
        pass
#endregion


def _looks_like_day_book_job(job: ImportJob, source_files: list[SourceFile]) -> bool:
    if is_day_book_source_type(job.source_type or ""):
        return True
    if job.source_type != "ai_generated":
        return False
    return any("序时簿" in (source_file.filename or "") for source_file in source_files)


class GeneratePayload(BaseModel):
    period_id: int | None = None
    period_start_date: date | None = None
    period_end_date: date | None = None
    accounting_judgment_policy: str = "compliant_default"


class CommitPayload(BaseModel):
    period_id: int | None = None
    period_start_date: date | None = None
    period_end_date: date | None = None
    drafts: list[dict]


class ManualEntryPayload(BaseModel):
    organization_name: str = "临时组织"
    period_id: int
    drafts: list[dict]


class ManualSwitchLogPayload(BaseModel):
    period_id: int
    reason: str | None = None
    recognized_evidence: list[dict] = []
    manual_fields: list[str] = []
    draft_metadata: dict = {}


def _clean_manual_entry_metadata(metadata: dict) -> dict:
    cleaned_metadata = dict(metadata or {})
    cleaned_metadata["source"] = "manual_entry"
    for key in (
        "is_blocked",
        "evidence_status",
        "missing_evidence",
        "missing_reason",
        "suggested_actions",
    ):
        cleaned_metadata.pop(key, None)
    return cleaned_metadata


def _validate_manual_entry_drafts(drafts: list[dict], period: AccountingPeriod) -> None:
    if not drafts:
        raise ValueError("人工凭证至少需要一条分录")

    debit_total = Decimal("0.00")
    credit_total = Decimal("0.00")
    voucher_no_set: set[str] = set()

    for index, draft in enumerate(drafts, start=1):
        row_no = draft.get("entry_line_no") or index
        if not str(draft.get("summary") or "").strip():
            raise ValueError(f"第 {row_no} 行摘要不能为空")
        if not str(draft.get("account_code") or "").strip():
            raise ValueError(f"第 {row_no} 行科目代码不能为空")
        if not str(draft.get("account_name") or "").strip():
            raise ValueError(f"第 {row_no} 行科目名称不能为空")

        voucher_no = str(draft.get("voucher_no") or "").strip()
        if not voucher_no:
            raise ValueError(f"第 {row_no} 行凭证号不能为空")
        voucher_no_set.add(voucher_no)

        try:
            voucher_date = date.fromisoformat(str(draft.get("voucher_date") or ""))
        except ValueError as exc:
            raise ValueError(f"第 {row_no} 行凭证日期格式不正确，请使用 YYYY-MM-DD") from exc
        if voucher_date < period.start_date or voucher_date > period.end_date:
            raise ValueError(
                f"第 {row_no} 行凭证日期不在会计期间 {period.period_code} 内，"
                "请检查凭证日期"
            )

        try:
            debit_amount = Decimal(str(draft.get("debit_amount", 0) or 0))
            credit_amount = Decimal(str(draft.get("credit_amount", 0) or 0))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"第 {row_no} 行借方或贷方金额格式不正确") from exc

        if debit_amount < 0 or credit_amount < 0:
            raise ValueError(f"第 {row_no} 行借方或贷方金额不能为负数")
        if debit_amount > 0 and credit_amount > 0:
            raise ValueError(f"第 {row_no} 行不能同时填写借方和贷方金额")
        if debit_amount == 0 and credit_amount == 0:
            raise ValueError(f"第 {row_no} 行至少填写借方或贷方金额")

        debit_total += debit_amount
        credit_total += credit_amount

    if len(voucher_no_set) > 1:
        raise ValueError("一次人工提交只能保存同一张凭证，请检查凭证号")
    if debit_total != credit_total:
        raise ValueError(
            f"人工凭证借贷不平衡：借方合计 {debit_total}，贷方合计 {credit_total}"
        )


def _get_fallback_period(db: Session, job: ImportJob) -> AccountingPeriod | None:
    query = db.query(AccountingPeriod).filter(AccountingPeriod.organization_id == job.organization_id)
    if job.ledger_id is not None:
        query = query.filter(
            (AccountingPeriod.ledger_id == job.ledger_id) | (AccountingPeriod.ledger_id.is_(None))
        )
    return query.order_by(AccountingPeriod.start_date.asc()).first()


def _batch_create_periods_if_needed(db: Session, job: ImportJob, start_date: date, end_date: date) -> dict:
    created_count = 0
    skipped_count = 0
    created_periods: list[AccountingPeriod] = []
    skipped_period_codes: list[str] = []

    existing_periods = (
        db.query(AccountingPeriod)
        .filter(AccountingPeriod.organization_id == job.organization_id)
        .all()
    )

    if job.ledger_id is not None:
        existing_periods = [p for p in existing_periods if p.ledger_id in (None, job.ledger_id)]

    current_year = start_date.year
    current_month = start_date.month
    end_year = end_date.year
    end_month = end_date.month

    while (current_year, current_month) <= (end_year, end_month):
        period_code = f"{current_year}-{current_month:02d}"
        period_start = date(current_year, current_month, 1)
        last_day = 31 if current_month in (1, 3, 5, 7, 8, 10, 12) else (30 if current_month != 2 else (29 if current_year % 4 == 0 and (current_year % 100 != 0 or current_year % 400 == 0) else 28))
        period_end = date(current_year, current_month, last_day)

        overlapped = False
        for existing in existing_periods:
            if existing.start_date <= period_end and existing.end_date >= period_start:
                overlapped = True
                break

        if overlapped:
            skipped_period_codes.append(period_code)
            skipped_count += 1
        else:
            period = AccountingPeriod(
                organization_id=job.organization_id,
                ledger_id=job.ledger_id,
                period_code=period_code,
                period_type="monthly",
                start_date=period_start,
                end_date=period_end,
                status="open",
            )
            db.add(period)
            created_periods.append(period)
            created_count += 1

        if current_month == 12:
            current_year += 1
            current_month = 1
        else:
            current_month += 1

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    for period in created_periods:
        db.refresh(period)

    return {
        "created_count": created_count,
        "skipped_count": skipped_count,
        "created_period_codes": [p.period_code for p in created_periods],
        "skipped_period_codes": skipped_period_codes,
    }


def _attach_auto_period_metadata(db: Session, job: ImportJob, drafts: list[dict]) -> dict:
    periods = (
        db.query(AccountingPeriod)
        .filter(AccountingPeriod.organization_id == job.organization_id)
        .order_by(AccountingPeriod.start_date.asc())
        .all()
    )
    if job.ledger_id is not None:
        periods = [period for period in periods if period.ledger_id in (None, job.ledger_id)]

    matched_count = 0
    missing_count = 0
    used_period_codes: set[str] = set()
    missing_months: set[str] = set()
    for draft in drafts:
        metadata = draft.get("metadata") or {}
        draft["metadata"] = metadata
        try:
            voucher_date = date.fromisoformat(str(draft.get("voucher_date") or ""))
        except ValueError:
            metadata["period_detection_status"] = "invalid_date"
            missing_count += 1
            continue
        matched = next((period for period in periods if period.start_date <= voucher_date <= period.end_date), None)
        if matched:
            metadata["period_detection_status"] = "matched"
            metadata["period_id"] = matched.id
            metadata["period_code"] = matched.period_code
            used_period_codes.add(matched.period_code)
            matched_count += 1
        else:
            metadata["period_detection_status"] = "missing_period"
            metadata["period_code"] = f"{voucher_date.year:04d}-{voucher_date.month:02d}"
            missing_months.add(metadata["period_code"])
            missing_count += 1
    return {
        "matched_count": matched_count,
        "missing_count": missing_count,
        "used_period_codes": sorted(used_period_codes),
        "missing_period_codes": sorted(missing_months),
    }


@router.post("/{job_id}/generate-entries")
def generate_entries(
    job_id: int,
    payload: GeneratePayload,
    db: Session = Depends(get_db),
) -> list[dict]:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")

    is_adaptive_mode = payload.period_start_date is not None and payload.period_end_date is not None
    batch_period_result: dict | None = None

    if is_adaptive_mode:
        if payload.period_start_date > payload.period_end_date:
            raise HTTPException(status_code=400, detail="期间范围开始日期不能晚于结束日期")
        batch_period_result = _batch_create_periods_if_needed(
            db, job, payload.period_start_date, payload.period_end_date
        )
        period = _get_fallback_period(db, job)
        if not period:
            raise HTTPException(status_code=404, detail="未找到可用于草稿生成的会计期间，请先维护会计期间")
    else:
        period = db.get(AccountingPeriod, payload.period_id) if payload.period_id else _get_fallback_period(db, job)
        if not period:
            raise HTTPException(status_code=404, detail="未找到可用于草稿生成的会计期间，请先维护会计期间")

    #region debug-point daybook-step3-performance
    performance_started_at = time.perf_counter()
    #endregion
    #region debug-point generate-entries-runtime
    source_files = db.query(SourceFile).filter(SourceFile.import_job_id == job.id).all()
    _debug_report_generate_entries(
        "generate_entries_before",
        {
            "job_id": job.id,
            "job_status": job.status,
            "job_source_type": job.source_type,
            "job_entry_count": job.entry_count,
            "draft_data_exists": job.draft_data is not None,
            "period_id": period.id,
            "is_adaptive_mode": is_adaptive_mode,
            "period_start_date": str(payload.period_start_date) if payload.period_start_date else None,
            "period_end_date": str(payload.period_end_date) if payload.period_end_date else None,
            "batch_period_result": batch_period_result,
            "source_files": [
                {
                    "id": source_file.id,
                    "filename": source_file.filename,
                    "file_type": source_file.file_type,
                    "text_extract_status": source_file.text_extract_status,
                    "has_extracted_text": bool(source_file.extracted_text),
                    "extracted_text_length": len(source_file.extracted_text or ""),
                }
                for source_file in source_files
            ],
        },
    )
    #endregion
    existing_entry_count = db.execute(
        text("SELECT COUNT(*) FROM accounting_entries WHERE import_job_id = :job_id"),
        {"job_id": job.id},
    ).scalar_one()
    if _looks_like_day_book_job(job, source_files) and existing_entry_count == 0:
        day_book_result = process_day_book_import(db, job)
        if day_book_result.success:
            job.status = "completed"
            job.entry_count = day_book_result.entries_created
            db.commit()
            db.refresh(job)
        elif job.source_type == "ai_generated":
            raise HTTPException(status_code=400, detail=day_book_result.error_message or "序时簿解析失败")
    drafts = entry_generation_service.generate_drafts(
        db,
        job,
        period,
        accounting_judgment_policy=payload.accounting_judgment_policy,
    )
    auto_period_summary = _attach_auto_period_metadata(db, job, drafts)
    #region debug-point auto-period-step3
    _debug_report_auto_period_step3(
        "auto_period_summary",
        {
            "job_id": job.id,
            "payload_period_id": payload.period_id,
            "fallback_period_id": period.id,
            **auto_period_summary,
        },
    )
    #endregion
    #region debug-point generate-entries-runtime
    _debug_report_generate_entries(
        "generate_entries_after",
        {
            "job_id": job.id,
            "draft_count": len(drafts),
            "drafts_preview": drafts[:3],
            "blocked_count": sum(1 for draft in drafts if (draft.get("metadata") or {}).get("is_blocked") is True),
        },
    )
    #endregion
    #region debug-point daybook-step3-performance
    voucher_numbers = [str(draft.get("voucher_no") or "") for draft in drafts]
    serialized_size = len(json.dumps(drafts, ensure_ascii=False, default=str))
    _debug_report_daybook_step3_performance(
        "generate_entries_payload",
        {
            "job_id": job.id,
            "draft_count": len(drafts),
            "blocked_count": sum(
                1 for draft in drafts if (draft.get("metadata") or {}).get("is_blocked") is True
            ),
            "entry_count": existing_entry_count,
            "distinct_voucher_count": len(set(voucher_numbers)),
            "first_vouchers": sorted(set(voucher_numbers))[:10],
            "last_vouchers": sorted(set(voucher_numbers))[-10:],
            "serialized_size_bytes": serialized_size,
            "elapsed_seconds": round(time.perf_counter() - performance_started_at, 3),
        },
    )
    #endregion
    return drafts


@router.post("/{job_id}/commit-entries")
def commit_entries(
    job_id: int,
    payload: CommitPayload,
    db: Session = Depends(get_db),
) -> dict:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    period = db.get(AccountingPeriod, payload.period_id) if payload.period_id else _get_fallback_period(db, job)
    if not period:
        raise HTTPException(status_code=404, detail="未找到可用于保存草稿的会计期间，请先维护会计期间")
    try:
        source_entry_ids = [
            int(draft.get("source_entry_id"))
            for draft in payload.drafts
            if (draft.get("metadata") or {}).get("accounting_flow") == "imported_day_book"
            and draft.get("source_entry_id") is not None
        ]
        if source_entry_ids:
            entries = (
                db.query(AccountingEntry)
                .filter(
                    AccountingEntry.import_job_id == job.id,
                    AccountingEntry.id.in_(source_entry_ids),
                )
                .all()
            )
        else:
            entries = entry_generation_service.commit_drafts(db, job, period, payload.drafts)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    job.entry_count = db.query(AccountingEntry).filter(AccountingEntry.import_job_id == job.id).count()
    job.status = "completed"
    db.commit()
    return {
        "count": len(entries),
        "entry_ids": [e.id for e in entries],
        "job_id": job.id,
    }


@router.post("/{job_id}/ai-draft/manual-switch-log")
def log_ai_draft_manual_switch(
    job_id: int,
    payload: ManualSwitchLogPayload,
    db: Session = Depends(get_db),
) -> dict:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    period = db.get(AccountingPeriod, payload.period_id)
    if not period:
        raise HTTPException(status_code=404, detail="会计期间不存在")

    switch_time = datetime.utcnow().isoformat()
    reason = payload.reason or "证据不足以达成真实性、准确性、截止性、充分性审计目的，转人工补充分录。"
    log_metadata = {
        "original_draft_metadata": payload.draft_metadata,
        "user": {"operator": "current_user_placeholder", "user_id": None},
        "switched_at": switch_time,
        "reason": reason,
        "recognized_evidence": payload.recognized_evidence,
        "manual_fields": payload.manual_fields,
        "audit_objective_note": "AI 的思维就是审计师的思维；证据无法支持业务真实性、准确性、截止性、充分性结论时，审计目的未达到，需人工补充判断。",
    }
    log = lifecycle_service.log_lifecycle_event(
        db=db,
        entity_type="import_job",
        entity_id=job.id,
        action="ai_draft_switched_to_manual",
        previous_status="ai_draft",
        new_status="manual_entry",
        reason=reason,
        operator_id=None,
        log_metadata=log_metadata,
    )
    return {"log_id": log.id, "action": log.action, "logged": True}


@router.post("/manual-entries")
def commit_manual_entries(
    payload: ManualEntryPayload,
    db: Session = Depends(get_db),
) -> dict:
    period = db.get(AccountingPeriod, payload.period_id)
    if not period:
        raise HTTPException(status_code=404, detail="会计期间不存在")

    organization = db.get(Organization, period.organization_id)
    if not organization:
        organization = Organization(name=payload.organization_name)
        db.add(organization)
        db.flush()

    job = ImportJob(
        organization_id=organization.id,
        ledger_id=period.ledger_id,
        status="created",
        source_type="manual_entry",
        file_count=0,
        entry_count=0,
    )
    db.add(job)
    db.flush()

    drafts: list[dict] = []
    for draft in payload.drafts:
        draft = dict(draft)
        draft["metadata"] = _clean_manual_entry_metadata(draft.get("metadata") or {})
        draft["tags"] = [
            tag for tag in (draft.get("tags") or [])
            if not (tag.get("tag_type") == "source" or tag.get("tag_value") == "source:manual_entry")
        ]
        drafts.append(draft)

    try:
        _validate_manual_entry_drafts(drafts, period)
        entries = entry_generation_service.commit_drafts(db, job, period, drafts)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    job.entry_count = len(entries)
    job.status = "completed"
    db.commit()
    return {
        "count": len(entries),
        "entry_ids": [e.id for e in entries],
        "job_id": job.id,
    }