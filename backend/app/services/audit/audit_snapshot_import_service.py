"""审计快照类（B2）结构化导入：preview → staging → confirm → 审计域表。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import (
    AuditAccountBalance,
    AuditGeneralLedgerLine,
    AuditGeneralLedgerSummary,
    ImportJob,
    SourceFile,
    StagingAccountBalance,
    StagingGeneralLedgerLine,
    StagingGeneralLedgerSummary,
)
from app.services.audit.audit_day_book_service import DayBookProcessingResult
from app.services.doc_parsing.import_routing_service import get_import_mode, get_structured_kind
from app.services.doc_parsing.structured_snapshot_parser import (
    parse_account_balance_rows,
    parse_general_ledger_line_rows,
    parse_general_ledger_summary_rows,
)
from app.storage.local_storage import resolve_storage_path


@dataclass
class SnapshotProcessingResult:
    success: bool
    rows_created: int = 0
    error_message: str | None = None


def _parse_snapshot_rows_from_job(db: Session, job: ImportJob, kind: str) -> tuple[list[dict[str, Any]], str | None]:
    files = db.query(SourceFile).filter(SourceFile.import_job_id == job.id).all()
    all_rows: list[dict[str, Any]] = []
    for source_file in files:
        if source_file.file_type.lower() not in {"xlsx", "xls", "csv", "tsv"}:
            continue
        path = resolve_storage_path(source_file.storage_path)
        if kind == "balances":
            rows = parse_account_balance_rows(path)
        elif kind == "general_ledger":
            rows = parse_general_ledger_line_rows(path)
        elif kind == "general_ledger_summary":
            rows = parse_general_ledger_summary_rows(path)
        else:
            return [], f"不支持的快照类型: {kind}"
        for row in rows:
            row["source_file_id"] = source_file.id
        all_rows.extend(rows)
    if not all_rows:
        return [], "未解析到有效快照数据，请检查表头是否包含科目、借贷或余额列"
    return all_rows, None


def preview_snapshot_import(db: Session, job: ImportJob) -> DayBookProcessingResult:
    kind = get_structured_kind(job.source_type)
    if kind not in {"balances", "general_ledger", "general_ledger_summary"}:
        return DayBookProcessingResult(success=False, error_message=f"不支持的快照类型: {job.source_type}")

    if kind == "balances":
        existing = db.query(StagingAccountBalance).filter(StagingAccountBalance.import_job_id == job.id).count()
    elif kind == "general_ledger":
        existing = db.query(StagingGeneralLedgerLine).filter(StagingGeneralLedgerLine.import_job_id == job.id).count()
    else:
        existing = db.query(StagingGeneralLedgerSummary).filter(StagingGeneralLedgerSummary.import_job_id == job.id).count()
    if existing > 0:
        return DayBookProcessingResult(success=True, entries_created=existing)

    rows, error = _parse_snapshot_rows_from_job(db, job, kind)
    if error:
        return DayBookProcessingResult(success=False, error_message=error)

    import_mode = get_import_mode(job.source_type)
    for row in rows:
        if kind == "balances":
            db.add(
                StagingAccountBalance(
                    import_job_id=job.id,
                    organization_id=job.organization_id,
                    project_id=job.project_id,
                    entity_org_id=job.organization_id,
                    import_mode=import_mode,
                    source_type=job.source_type,
                    account_code=row.get("account_code"),
                    account_name=row.get("account_name"),
                    period_code=row.get("period_code"),
                    opening_balance=row.get("opening_balance"),
                    debit_total=row.get("debit_total"),
                    credit_total=row.get("credit_total"),
                    closing_balance=row.get("closing_balance"),
                    direction=row.get("direction"),
                    review_status="draft",
                )
            )
        elif kind == "general_ledger":
            db.add(
                StagingGeneralLedgerLine(
                    import_job_id=job.id,
                    organization_id=job.organization_id,
                    project_id=job.project_id,
                    entity_org_id=job.organization_id,
                    import_mode=import_mode,
                    source_type=job.source_type,
                    account_code=row.get("account_code"),
                    account_name=row.get("account_name"),
                    voucher_date=row.get("voucher_date"),
                    voucher_no=row.get("voucher_no"),
                    summary=row.get("summary"),
                    debit=row.get("debit"),
                    credit=row.get("credit"),
                    running_balance=row.get("running_balance"),
                    direction=row.get("direction"),
                    review_status="draft",
                )
            )
        else:
            db.add(
                StagingGeneralLedgerSummary(
                    import_job_id=job.id,
                    organization_id=job.organization_id,
                    project_id=job.project_id,
                    entity_org_id=job.organization_id,
                    import_mode=import_mode,
                    source_type=job.source_type,
                    account_code=row.get("account_code"),
                    account_name=row.get("account_name"),
                    period_code=row.get("period_code"),
                    opening_balance=row.get("opening_balance"),
                    debit_total=row.get("debit_total"),
                    credit_total=row.get("credit_total"),
                    closing_balance=row.get("closing_balance"),
                    direction=row.get("direction"),
                    review_status="draft",
                )
            )
    db.commit()
    return DayBookProcessingResult(success=True, entries_created=len(rows))


def confirm_snapshot_import(db: Session, job: ImportJob) -> DayBookProcessingResult:
    kind = get_structured_kind(job.source_type)
    if not job.project_id:
        return DayBookProcessingResult(success=False, error_message="审计快照导入需要指定 project_id")

    entity_org_id = job.organization_id
    created = 0

    if kind == "balances":
        staging_rows = (
            db.query(StagingAccountBalance)
            .filter(StagingAccountBalance.import_job_id == job.id)
            .all()
        )
        if not staging_rows:
            return DayBookProcessingResult(success=False, error_message="没有可确认的草稿余额行")
        for row in staging_rows:
            db.add(
                AuditAccountBalance(
                    project_id=job.project_id,
                    entity_org_id=entity_org_id,
                    import_job_id=job.id,
                    account_code=row.account_code,
                    account_name=row.account_name,
                    opening_balance=row.opening_balance,
                    debit_total=row.debit_total,
                    credit_total=row.credit_total,
                    closing_balance=row.closing_balance,
                    direction=row.direction,
                    review_status="pending",
                    post_status="draft",
                )
            )
            created += 1
        db.query(StagingAccountBalance).filter(StagingAccountBalance.import_job_id == job.id).delete(
            synchronize_session=False
        )
    elif kind == "general_ledger":
        staging_rows = (
            db.query(StagingGeneralLedgerLine)
            .filter(StagingGeneralLedgerLine.import_job_id == job.id)
            .all()
        )
        if not staging_rows:
            return DayBookProcessingResult(success=False, error_message="没有可确认的草稿明细账行")
        for row in staging_rows:
            db.add(
                AuditGeneralLedgerLine(
                    project_id=job.project_id,
                    entity_org_id=entity_org_id,
                    import_job_id=job.id,
                    account_code=row.account_code,
                    account_name=row.account_name,
                    voucher_date=row.voucher_date,
                    voucher_no=row.voucher_no,
                    summary=row.summary,
                    debit=row.debit,
                    credit=row.credit,
                    running_balance=row.running_balance,
                    direction=row.direction,
                    review_status="pending",
                )
            )
            created += 1
        db.query(StagingGeneralLedgerLine).filter(StagingGeneralLedgerLine.import_job_id == job.id).delete(
            synchronize_session=False
        )
    elif kind == "general_ledger_summary":
        staging_rows = (
            db.query(StagingGeneralLedgerSummary)
            .filter(StagingGeneralLedgerSummary.import_job_id == job.id)
            .all()
        )
        if not staging_rows:
            return DayBookProcessingResult(success=False, error_message="没有可确认的草稿总账行")
        for row in staging_rows:
            db.add(
                AuditGeneralLedgerSummary(
                    project_id=job.project_id,
                    entity_org_id=entity_org_id,
                    import_job_id=job.id,
                    account_code=row.account_code,
                    account_name=row.account_name,
                    opening_balance=row.opening_balance,
                    debit_total=row.debit_total,
                    credit_total=row.credit_total,
                    closing_balance=row.closing_balance,
                    direction=row.direction,
                    review_status="pending",
                    post_status="draft",
                )
            )
            created += 1
        db.query(StagingGeneralLedgerSummary).filter(
            StagingGeneralLedgerSummary.import_job_id == job.id
        ).delete(synchronize_session=False)
    else:
        return DayBookProcessingResult(success=False, error_message=f"不支持的快照类型: {job.source_type}")

    db.commit()
    return DayBookProcessingResult(success=True, entries_created=created)


def cancel_snapshot_import(db: Session, job: ImportJob) -> None:
    kind = get_structured_kind(job.source_type)
    if kind == "balances":
        db.query(StagingAccountBalance).filter(StagingAccountBalance.import_job_id == job.id).delete(
            synchronize_session=False
        )
    elif kind == "general_ledger":
        db.query(StagingGeneralLedgerLine).filter(StagingGeneralLedgerLine.import_job_id == job.id).delete(
            synchronize_session=False
        )
    elif kind == "general_ledger_summary":
        db.query(StagingGeneralLedgerSummary).filter(
            StagingGeneralLedgerSummary.import_job_id == job.id
        ).delete(synchronize_session=False)
    job.status = "cancelled"
    db.commit()
