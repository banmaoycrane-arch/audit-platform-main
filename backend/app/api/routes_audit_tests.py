from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import (
    AccountingEntry,
    AuditFinding,
    AuditFindingReviewAction,
    AuditReport,
    ImportJob,
    SourceFile,
)
from app.db.session import get_db
from app.services.audit_test_service import audit_test_service
from app.services.ledger_service import ledger_service

router = APIRouter(prefix="/api/audit-tests", tags=["audit-tests"])

VALID_REVIEW_ACTIONS = {"confirmed", "false_positive", "resolved", "pending"}


class ReviewPayload(BaseModel):
    action: str
    comment: str | None = None


def _file_type(filename: str, file_type: str | None) -> str:
    value = f"{file_type or ''} {filename}".lower()
    if "contract" in value or "合同" in value:
        return "contract"
    if "invoice" in value or "发票" in value:
        return "invoice"
    if "inventory" in value or "入库" in value or "出库" in value:
        return "inventory"
    if "bank" in value or "银行" in value or "流水" in value or "回单" in value:
        return "bank_statement"
    return "other"


def _reset_ledgers() -> None:
    ledger_service.contract_ledger.clear()
    ledger_service.invoice_ledger.clear()
    ledger_service.inventory_ledger.clear()
    ledger_service.bank_statement_ledger.clear()
    ledger_service.payroll_ledger.clear()
    ledger_service.business_links.clear()
    audit_test_service.clear_findings()


def _load_job_to_ledgers(db: Session, job: ImportJob) -> None:
    _reset_ledgers()

    files = db.query(SourceFile).filter(SourceFile.import_job_id == job.id).all()
    for source_file in files:
        evidence_type = _file_type(source_file.filename, source_file.file_type)
        data = {
            "amount": None,
            "total_amount": None,
            "contract_amount": None,
            "confidence": 0.8,
        }
        if evidence_type == "contract":
            ledger_service.add_contract(data, source_file.filename)
        elif evidence_type == "invoice":
            ledger_service.add_invoice(data, source_file.filename)
        elif evidence_type == "inventory":
            ledger_service.add_inventory(data, source_file.filename)
        elif evidence_type == "bank_statement":
            ledger_service.add_bank_statement(data, source_file.filename)

    entries = db.query(AccountingEntry).filter(AccountingEntry.import_job_id == job.id).all()
    for entry in entries:
        amount = float(entry.debit_amount or entry.credit_amount or 0)
        data = {
            "invoice_number": entry.voucher_no,
            "buyer_name": entry.original_entity_name,
            "seller_name": entry.counterparty,
            "total_amount": amount,
            "invoice_date": entry.voucher_date.isoformat() if entry.voucher_date else None,
            "confidence": 0.7,
            "account_name": entry.account_name,
            "summary": entry.summary,
        }
        ledger_service.add_invoice(data, f"凭证-{entry.voucher_no or '未编号'}-行{entry.entry_line_no}-{entry.id}")


def _report_to_dict(report) -> dict:
    return report.model_dump(mode="json")


def _save_audit_report(db: Session, job_id: int, payload: dict) -> AuditReport:
    report = db.query(AuditReport).filter(AuditReport.import_job_id == job_id).first()
    if report:
        report.report_payload = payload
        report.updated_at = datetime.utcnow()
        return report
    report = AuditReport(import_job_id=job_id, report_payload=payload)
    db.add(report)
    return report


def _finding_to_dict(finding: AuditFinding) -> dict[str, Any]:
    return {
        "id": finding.finding_uuid,
        "db_id": finding.id,
        "finding_type": finding.finding_type,
        "severity": finding.severity,
        "business_type": finding.business_type or "",
        "related_entries": list(finding.related_entries or []),
        "related_files": list(finding.related_files or []),
        "finding_title": finding.finding_title,
        "finding_description": finding.finding_description or "",
        "audit_procedure": finding.audit_procedure or "",
        "audit_conclusion": finding.audit_conclusion or "",
        "risk_statement": finding.risk_statement or "",
        "recommendation": finding.recommendation or "",
        "metadata": dict(finding.finding_metadata or {}),
        "status": finding.status,
    }


def _persist_findings(db: Session, job_id: int, findings_payload: list[dict]) -> list[AuditFinding]:
    db.query(AuditFinding).filter(AuditFinding.job_id == job_id).delete()
    db.flush()
    persisted: list[AuditFinding] = []
    for item in findings_payload:
        finding = AuditFinding(
            job_id=job_id,
            finding_uuid=str(item.get("id", "")),
            finding_type=str(item.get("finding_type", "unknown")),
            severity=str(item.get("severity", "low")),
            business_type=item.get("business_type"),
            finding_title=str(item.get("finding_title", ""))[:500],
            finding_description=str(item.get("finding_description", "")),
            audit_procedure=str(item.get("audit_procedure", "")),
            audit_conclusion=str(item.get("audit_conclusion", "")),
            risk_statement=str(item.get("risk_statement", "")),
            recommendation=str(item.get("recommendation", "")),
            related_entries=item.get("related_entries", []) or [],
            related_files=item.get("related_files", []) or [],
            finding_metadata=item.get("metadata", {}) or {},
            status=str(item.get("status", "pending")),
        )
        db.add(finding)
        persisted.append(finding)
    db.flush()
    return persisted


@router.post("/{job_id}/run")
def run_audit_tests(job_id: int, db: Session = Depends(get_db)) -> dict:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")

    _load_job_to_ledgers(db, job)
    report = audit_test_service.generate_report(
        period="当前导入任务",
        scope=f"导入任务 {job_id}",
    )
    payload = _report_to_dict(report)

    persisted = _persist_findings(db, job_id, payload.get("findings", []))
    payload["findings"] = [_finding_to_dict(item) for item in persisted]
    _save_audit_report(db, job_id, payload)
    db.commit()

    return payload


@router.get("/{job_id}/report")
def get_audit_report(job_id: int, db: Session = Depends(get_db)) -> dict:
    report = db.query(AuditReport).filter(AuditReport.import_job_id == job_id).first()
    if report:
        return dict(report.report_payload or {})
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    raise HTTPException(status_code=404, detail="审计测试报告不存在，请先执行测试")


@router.get("/{job_id}/findings")
def get_audit_findings(job_id: int, db: Session = Depends(get_db)) -> list[dict]:
    findings = db.query(AuditFinding).filter(AuditFinding.job_id == job_id).all()
    if findings:
        return [_finding_to_dict(item) for item in findings]
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    raise HTTPException(status_code=404, detail="审计发现不存在，请先执行测试")


@router.patch("/findings/{finding_id}/review")
def review_audit_finding(
    finding_id: int,
    payload: ReviewPayload,
    db: Session = Depends(get_db),
) -> dict:
    if payload.action not in VALID_REVIEW_ACTIONS:
        raise HTTPException(status_code=400, detail="非法的复核动作")
    finding = db.get(AuditFinding, finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="审计发现不存在")
    finding.status = payload.action
    finding.updated_at = datetime.utcnow()
    db.add(
        AuditFindingReviewAction(
            finding_id=finding.id,
            action=payload.action,
            comment=payload.comment,
        )
    )
    db.commit()
    db.refresh(finding)
    return _finding_to_dict(finding)
