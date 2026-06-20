from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import AccountingPeriod, ImportJob, Organization
from app.db.session import get_db
from app.services import entry_generation_service, lifecycle_service

router = APIRouter(prefix="/api/import-jobs", tags=["entry-generation"])


class GeneratePayload(BaseModel):
    period_id: int


class CommitPayload(BaseModel):
    period_id: int
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


@router.post("/{job_id}/generate-entries")
def generate_entries(
    job_id: int,
    payload: GeneratePayload,
    db: Session = Depends(get_db),
) -> list[dict]:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    period = db.get(AccountingPeriod, payload.period_id)
    if not period:
        raise HTTPException(status_code=404, detail="会计期间不存在")
    drafts = entry_generation_service.generate_drafts(db, job, period)
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
    period = db.get(AccountingPeriod, payload.period_id)
    if not period:
        raise HTTPException(status_code=404, detail="会计期间不存在")
    try:
        entries = entry_generation_service.commit_drafts(db, job, period, payload.drafts)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    job.entry_count = (job.entry_count or 0) + len(entries)
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