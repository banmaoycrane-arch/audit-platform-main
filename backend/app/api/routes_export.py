import csv
import io
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Iterable

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.db.models import AccountingEntry, ImportJob, StagingAccountingEntry
from app.db.session import get_db
from app.models.ledger import Ledger
from app.services.accounting.export_filename_service import (
    build_import_job_export_filename,
    content_disposition_attachment,
)

router = APIRouter(prefix="/api/import-jobs", tags=["export"])

SUPPORTED_FORMATS = {"xlsx", "csv", "json"}
POSTABLE_REVIEW_STATUSES = {"verified", "ready"}


def _entry_is_postable(entry: AccountingEntry) -> bool:
    if entry.review_status in POSTABLE_REVIEW_STATUSES:
        return True
    # 序时簿确认入账后历史数据为 pending，允许 Step5 过账导出
    return (
        entry.review_status == "pending"
        and entry.import_job_id is not None
        and entry.entry_source == "auto"
    )

COLUMNS = [
    ("voucher_no", "凭证号"),
    ("entry_line_no", "行号"),
    ("voucher_date", "日期"),
    ("account_code", "科目代码"),
    ("account_name", "科目名称"),
    ("summary", "摘要"),
    ("debit_amount", "借方金额"),
    ("credit_amount", "贷方金额"),
    ("counterparty", "对方单位"),
]


def _serialize(entry: AccountingEntry) -> dict[str, Any]:
    def _as_str(value: Any) -> Any:
        if value is None:
            return ""
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        return value

    return {
        key: _as_str(getattr(entry, key, None))
        for key, _ in COLUMNS
    }


def _entries_to_xlsx(entries: Iterable[AccountingEntry]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "凭证清单"
    ws.append([label for _, label in COLUMNS])
    for entry in entries:
        row = _serialize(entry)
        ws.append([row[key] for key, _ in COLUMNS])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _entries_to_csv(entries: Iterable[AccountingEntry]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([label for _, label in COLUMNS])
    for entry in entries:
        row = _serialize(entry)
        writer.writerow([row[key] for key, _ in COLUMNS])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def _entries_to_json(entries: Iterable[AccountingEntry]) -> bytes:
    payload = [_serialize(e) for e in entries]
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


@router.post("/{job_id}/post")
def post_import_job_entries(
    job_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")

    entries = (
        db.query(AccountingEntry)
        .filter(AccountingEntry.import_job_id == job_id)
        .all()
    )
    if not entries:
        staging_count = (
            db.query(StagingAccountingEntry)
            .filter(StagingAccountingEntry.import_job_id == job_id)
            .count()
        )
        if staging_count:
            raise HTTPException(
                status_code=400,
                detail="尚未确认入账：请先在 Step4 完成凭证复核；本页导出将自动确认入账",
            )
        raise HTTPException(status_code=400, detail="该导入任务下没有可入账的分录")

    unreviewed = [entry for entry in entries if not _entry_is_postable(entry)]
    if unreviewed:
        sample_ids = [entry.id for entry in unreviewed[:20]]
        raise HTTPException(
            status_code=400,
            detail={
                "message": "存在未复核通过的分录（需 verified 或 ready）",
                "unreviewed_count": len(unreviewed),
                "sample_entry_ids": sample_ids,
            },
        )

    now = datetime.now(timezone.utc)
    posted_count = 0
    for entry in entries:
        if entry.post_status != "posted":
            entry.post_status = "posted"
            entry.posted_at = now
            posted_count += 1
    if job.status == "preview":
        job.status = "completed"
        job.entry_count = len(entries)
    db.commit()

    return {
        "job_id": job_id,
        "posted": posted_count,
        "total": len(entries),
        "posted_at": now.isoformat(),
    }


@router.get("/{job_id}/export")
def export_import_job(
    job_id: int,
    format: str = "xlsx",
    db: Session = Depends(get_db),
) -> StreamingResponse:
    fmt = format.lower()
    if fmt not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的导出格式：{format}，仅支持 xlsx/csv/json",
        )
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")

    entries = (
        db.query(AccountingEntry)
        .filter(
            AccountingEntry.import_job_id == job_id,
            AccountingEntry.post_status == "posted",
        )
        .order_by(AccountingEntry.voucher_no, AccountingEntry.entry_line_no)
        .all()
    )

    if fmt == "xlsx":
        body = _entries_to_xlsx(entries)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif fmt == "csv":
        body = _entries_to_csv(entries)
        media = "text/csv; charset=utf-8"
    else:
        body = _entries_to_json(entries)
        media = "application/json; charset=utf-8"

    ledger_name = None
    if job.ledger_id is not None:
        ledger = db.get(Ledger, job.ledger_id)
        ledger_name = ledger.name if ledger else None
    filename = build_import_job_export_filename(job, ledger_name=ledger_name, fmt=fmt)

    return StreamingResponse(
        io.BytesIO(body),
        media_type=media,
        headers={"Content-Disposition": content_disposition_attachment(filename)},
    )
