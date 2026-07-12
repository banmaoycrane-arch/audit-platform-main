"""导入任务清理：识别卡死/废弃任务并释放 staging 与上传文件空间。"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import (
    AccountingEntry,
    AuditReport,
    AuditRisk,
    AuditTask,
    DocumentParsingTask,
    ImportJob,
    ReviewAction,
    RiskEvidence,
    SourceFile,
    StagingAccountBalance,
    StagingAccountingEntry,
    StagingGeneralLedgerLine,
    StagingGeneralLedgerSummary,
    Voucher,
)
from app.storage.local_storage import resolve_storage_path

# 可直接清理的状态（不含已正式入账完成的 completed）
CLEANABLE_STATUSES = frozenset({
    "created",
    "queued",
    "processing",
    "draft",
    "failed",
    "cancelled",
    "preview",
})

PROTECTED_STATUSES = frozenset({"completed"})

# processing / queued 超过该时长视为卡死
STUCK_ACTIVE_HOURS = 1


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _job_age_hours(job: ImportJob, now: datetime | None = None) -> float | None:
    if not job.created_at:
        return None
    created = job.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    ref = now or _utc_now()
    return (ref - created).total_seconds() / 3600.0


def _is_stuck_job(job: ImportJob, now: datetime | None = None) -> bool:
    if job.status not in {"processing", "queued"}:
        return False
    age = _job_age_hours(job, now)
    return age is not None and age >= STUCK_ACTIVE_HOURS


def _staging_row_count(db: Session, job_id: int) -> int:
    total = 0
    for model in (
        StagingAccountingEntry,
        StagingAccountBalance,
        StagingGeneralLedgerLine,
        StagingGeneralLedgerSummary,
    ):
        total += (
            db.query(func.count())
            .select_from(model)
            .filter(model.import_job_id == job_id)
            .scalar()
            or 0
        )
    return int(total)


def _has_confirmed_ledger_data(db: Session, job_id: int) -> bool:
    if db.query(Voucher.id).filter(Voucher.import_job_id == job_id).first():
        return True
    if db.query(AccountingEntry.id).filter(AccountingEntry.import_job_id == job_id).first():
        return True
    return False


def _delete_related_records(db: Session, job_id: int) -> int:
    deleted = 0
    risk_ids = [
        row[0]
        for row in db.query(AuditRisk.id).filter(AuditRisk.import_job_id == job_id).all()
    ]
    if risk_ids:
        deleted += (
            db.query(RiskEvidence)
            .filter(RiskEvidence.risk_id.in_(risk_ids))
            .delete(synchronize_session=False)
            or 0
        )
        deleted += (
            db.query(ReviewAction)
            .filter(ReviewAction.risk_id.in_(risk_ids))
            .delete(synchronize_session=False)
            or 0
        )
        deleted += (
            db.query(AuditRisk)
            .filter(AuditRisk.import_job_id == job_id)
            .delete(synchronize_session=False)
            or 0
        )
    deleted += (
        db.query(AuditReport)
        .filter(AuditReport.import_job_id == job_id)
        .delete(synchronize_session=False)
        or 0
    )
    deleted += (
        db.query(DocumentParsingTask)
        .filter(DocumentParsingTask.import_job_id == job_id)
        .delete(synchronize_session=False)
        or 0
    )
    db.query(AuditTask).filter(AuditTask.import_job_id == job_id).update(
        {AuditTask.import_job_id: None},
        synchronize_session=False,
    )
    return deleted


def _delete_staging_for_job(db: Session, job_id: int) -> int:
    deleted = 0
    for model in (
        StagingAccountingEntry,
        StagingAccountBalance,
        StagingGeneralLedgerLine,
        StagingGeneralLedgerSummary,
    ):
        deleted += (
            db.query(model)
            .filter(model.import_job_id == job_id)
            .delete(synchronize_session=False)
            or 0
        )
    try:
        from app.services.audit.staging_preview_cache import invalidate_staging_preview_cache

        invalidate_staging_preview_cache(job_id)
    except Exception:
        pass
    return deleted


def _delete_source_files(db: Session, job_id: int, *, delete_disk: bool) -> int:
    files = db.query(SourceFile).filter(SourceFile.import_job_id == job_id).all()
    removed = 0
    for item in files:
        if delete_disk and item.storage_path:
            try:
                path = resolve_storage_path(item.storage_path)
                if os.path.isfile(path):
                    os.remove(path)
            except OSError:
                pass
        db.delete(item)
        removed += 1
    return removed


def _job_summary_row(db: Session, job: ImportJob, now: datetime | None = None) -> dict[str, Any]:
    stuck = _is_stuck_job(job, now)
    cleanable = job.status in CLEANABLE_STATUSES or stuck
    stuck_reason = None
    if stuck:
        stuck_reason = f"{job.status} 已超过 {STUCK_ACTIVE_HOURS} 小时未结束"
    elif job.status == "created" and job.file_count == 0:
        stuck_reason = "已创建但未上传文件"
    elif job.status == "failed":
        stuck_reason = job.error_message or "解析失败"
    return {
        "id": job.id,
        "status": job.status,
        "source_type": job.source_type,
        "file_count": job.file_count,
        "entry_count": job.entry_count,
        "staging_rows": _staging_row_count(db, job.id),
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "ledger_id": job.ledger_id,
        "cleanable": cleanable and job.status not in PROTECTED_STATUSES,
        "stuck": stuck or job.status in {"failed", "draft"} or (job.status == "created" and job.file_count == 0),
        "stuck_reason": stuck_reason,
    }


def get_import_job_cleanup_summary(
    db: Session,
    *,
    ledger_id: int | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    query = db.query(ImportJob).order_by(ImportJob.id.desc())
    if ledger_id is not None:
        query = query.filter(ImportJob.ledger_id == ledger_id)
    jobs = query.limit(limit).all()
    now = _utc_now()

    by_status: dict[str, int] = {}
    cleanable_jobs: list[dict[str, Any]] = []
    stuck_jobs: list[dict[str, Any]] = []
    total_staging_rows = 0

    for job in jobs:
        by_status[job.status] = by_status.get(job.status, 0) + 1
        row = _job_summary_row(db, job, now)
        total_staging_rows += row["staging_rows"]
        if row["cleanable"]:
            cleanable_jobs.append(row)
        if row["stuck"]:
            stuck_jobs.append(row)

    return {
        "ledger_id": ledger_id,
        "total_jobs": len(jobs),
        "by_status": by_status,
        "cleanable_count": len(cleanable_jobs),
        "stuck_count": len(stuck_jobs),
        "total_staging_rows": total_staging_rows,
        "stuck_active_hours": STUCK_ACTIVE_HOURS,
        "cleanable_statuses": sorted(CLEANABLE_STATUSES),
        "jobs": [_job_summary_row(db, job, now) for job in jobs],
        "cleanable_jobs": cleanable_jobs,
        "stuck_jobs": stuck_jobs,
    }


def purge_import_job(
    db: Session,
    job_id: int,
    *,
    delete_files: bool = True,
) -> dict[str, Any]:
    job = db.get(ImportJob, job_id)
    if not job:
        raise ValueError(f"导入任务 #{job_id} 不存在")
    if job.status in PROTECTED_STATUSES:
        raise ValueError(f"任务 #{job_id} 状态为 {job.status}，已正式完成，不可清理")
    if _has_confirmed_ledger_data(db, job_id):
        raise ValueError(f"任务 #{job_id} 已产生正式凭证/分录，不可清理")

    related_deleted = _delete_related_records(db, job_id)
    staging_deleted = _delete_staging_for_job(db, job_id)
    files_deleted = _delete_source_files(db, job_id, delete_disk=delete_files)
    db.delete(job)
    db.commit()
    return {
        "job_id": job_id,
        "purged": True,
        "staging_rows_deleted": staging_deleted,
        "related_records_deleted": related_deleted,
        "source_files_deleted": files_deleted,
    }


def bulk_purge_import_jobs(
    db: Session,
    *,
    ledger_id: int | None = None,
    job_ids: list[int] | None = None,
    statuses: list[str] | None = None,
    keep_job_ids: list[int] | None = None,
    stuck_only: bool = False,
    delete_files: bool = True,
) -> dict[str, Any]:
    keep = set(keep_job_ids or [])
    query = db.query(ImportJob)
    if ledger_id is not None:
        query = query.filter(ImportJob.ledger_id == ledger_id)
    if job_ids:
        query = query.filter(ImportJob.id.in_(job_ids))
    jobs = query.order_by(ImportJob.id.asc()).all()
    now = _utc_now()

    purged: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for job in jobs:
        if job.id in keep:
            skipped.append({"job_id": job.id, "reason": "在保留列表中"})
            continue
        if job.status in PROTECTED_STATUSES:
            skipped.append({"job_id": job.id, "reason": f"状态 {job.status} 不可清理"})
            continue
        if not job_ids:
            if statuses and job.status not in statuses and not _is_stuck_job(job, now):
                skipped.append({"job_id": job.id, "reason": "不在选定状态范围"})
                continue
        if stuck_only and not _is_stuck_job(job, now) and job.status not in {"failed", "draft", "cancelled"}:
            if not (job.status == "created" and job.file_count == 0):
                skipped.append({"job_id": job.id, "reason": "非卡死/废弃任务"})
                continue
        try:
            purged.append(purge_import_job(db, job.id, delete_files=delete_files))
        except ValueError as exc:
            skipped.append({"job_id": job.id, "reason": str(exc)})

    return {
        "purged_count": len(purged),
        "skipped_count": len(skipped),
        "purged": purged,
        "skipped": skipped,
    }
