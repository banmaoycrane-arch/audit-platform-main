"""底稿资料自动归档服务。

在解析/台账登记完成后，根据项目、期间、模块维度为 SourceFile 生成虚拟归档路径，
写入 notes 字段，便于用户在项目范围内检索与管理底稿资料。
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import ImportJob, SourceFile
from app.models.project import Project
from app.models.project_ledger import ProjectLedger

ARCHIVE_CATEGORIES: dict[str, str] = {
    "tax_invoice": "税务底稿",
    "bank_cash_flow": "银行资金底稿",
    "counterparty_ledger": "往来账款底稿",
    "purchase": "采购底稿",
    "sales": "销售底稿",
    "inventory_receipt": "库存底稿",
    "payroll": "薪酬底稿",
    "general": "通用底稿",
    "accounting_voucher": "会计凭证底稿",
    "day_book": "序时簿底稿",
    "structured_ledger": "结构化序时簿",
    "unknown": "待分类底稿",
}

DOCUMENT_FOLDER_LABELS: dict[str, str] = {
    "invoice": "发票",
    "bank_statement": "银行流水",
    "contract": "合同",
    "inventory_receipt": "入库单",
    "payroll": "薪酬资料",
    "general": "通用资料",
    "structured_ledger": "序时簿",
    "unknown": "未识别资料",
}

_UNCLASSIFIED_PERIOD = "未分类期间"
_UNASSIGNED_PROJECT = "未关联项目"


def _load_notes(source_file: SourceFile) -> dict[str, Any]:
    if not source_file.notes:
        return {}
    try:
        parsed = json.loads(source_file.notes)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _save_notes(source_file: SourceFile, notes: dict[str, Any]) -> None:
    source_file.notes = json.dumps(notes, ensure_ascii=False)


def load_archive_metadata(source_file: SourceFile) -> dict[str, Any] | None:
    archive = _load_notes(source_file).get("archive")
    return archive if isinstance(archive, dict) else None


def resolve_project_for_ledger(db: Session, ledger_id: int | None) -> Project | None:
    if not ledger_id:
        return None
    link = (
        db.query(ProjectLedger)
        .filter(ProjectLedger.ledger_id == ledger_id)
        .order_by(ProjectLedger.id.desc())
        .first()
    )
    if not link:
        return None
    return db.get(Project, link.project_id)


def _sanitize_segment(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", value.strip())
    return cleaned or "未命名"


def _infer_period_code(parse_feedback: dict[str, Any]) -> str:
    voucher_date = parse_feedback.get("voucher_date")
    if voucher_date:
        text = str(voucher_date).strip()
        if len(text) >= 7 and text[4] == "-":
            return text[:7]
        if len(text) >= 6:
            return f"{text[:4]}-{text[4:6]}"
    period_code = parse_feedback.get("period_code")
    if period_code:
        return str(period_code).strip()
    return _UNCLASSIFIED_PERIOD


def _primary_module_key(
    parse_feedback: dict[str, Any],
    module_registrations: list[dict[str, Any]] | None,
) -> str:
    if module_registrations:
        for item in module_registrations:
            if not item.get("semantic_only"):
                return str(item.get("module_key") or "general")
        return str(module_registrations[0].get("module_key") or "general")
    register_type = parse_feedback.get("register_type") or parse_feedback.get("document_type")
    if register_type in ARCHIVE_CATEGORIES:
        return str(register_type)
    mapping = {
        "invoice": "tax_invoice",
        "bank_statement": "bank_cash_flow",
        "contract": "counterparty_ledger",
        "inventory_receipt": "inventory_receipt",
        "payroll": "payroll",
        "structured_ledger": "structured_ledger",
    }
    document_type = str(parse_feedback.get("document_type") or "general")
    return mapping.get(document_type, "general")


def build_archive_path(
    project_name: str,
    period_code: str,
    archive_category: str,
    document_folder: str,
) -> str:
    return "/".join(
        _sanitize_segment(part)
        for part in (project_name, period_code, archive_category, document_folder)
    )


def build_archive_context(
    *,
    project: Project | None,
    parse_feedback: dict[str, Any],
    module_registrations: list[dict[str, Any]] | None = None,
    source_type: str | None = None,
) -> dict[str, Any]:
    project_name = project.name if project else _UNASSIGNED_PROJECT
    period_code = _infer_period_code(parse_feedback)
    module_key = _primary_module_key(parse_feedback, module_registrations)

    if source_type in {"ledger_day_book", "audit_day_book"}:
        module_key = "day_book"

    archive_category = ARCHIVE_CATEGORIES.get(module_key, ARCHIVE_CATEGORIES["general"])
    document_type = str(parse_feedback.get("document_type") or parse_feedback.get("register_type") or "unknown")
    document_folder = DOCUMENT_FOLDER_LABELS.get(document_type, parse_feedback.get("document_type_label") or "资料")

    archive_path = build_archive_path(project_name, period_code, archive_category, str(document_folder))
    module_keys = [str(item.get("module_key")) for item in (module_registrations or []) if item.get("module_key")]
    if module_key not in module_keys:
        module_keys.insert(0, module_key)

    return {
        "project_id": project.id if project else None,
        "project_name": project_name,
        "ledger_id": parse_feedback.get("ledger_id"),
        "period_code": period_code,
        "archive_category": archive_category,
        "archive_folder": str(document_folder),
        "archive_path": archive_path,
        "module_key": module_key,
        "module_keys": module_keys,
        "document_type": document_type,
        "document_type_label": parse_feedback.get("document_type_label"),
        "counterparty": parse_feedback.get("counterparty"),
        "status": "archived",
        "archived_at": datetime.utcnow().isoformat(),
    }


def auto_archive_draft(
    db: Session,
    source_file: SourceFile,
    parse_feedback: dict[str, Any],
    *,
    module_registrations: list[dict[str, Any]] | None = None,
    source_type: str | None = None,
    job: ImportJob | None = None,
) -> dict[str, Any]:
    """解析完成后自动归档底稿，返回归档上下文。"""
    ledger_id = source_file.ledger_id
    if ledger_id is None and job is not None:
        ledger_id = job.ledger_id
    if ledger_id is None and source_file.import_job_id:
        linked_job = db.get(ImportJob, source_file.import_job_id)
        if linked_job:
            ledger_id = linked_job.ledger_id

    feedback = dict(parse_feedback)
    feedback["ledger_id"] = ledger_id
    project = resolve_project_for_ledger(db, ledger_id)
    archive = build_archive_context(
        project=project,
        parse_feedback=feedback,
        module_registrations=module_registrations,
        source_type=source_type or (job.source_type if job else None),
    )

    notes = _load_notes(source_file)
    notes["archive"] = archive
    _save_notes(source_file, notes)
    if source_file.ledger_id is None and ledger_id is not None:
        source_file.ledger_id = ledger_id

    return archive


def list_project_archived_files(db: Session, project_id: int, ledger_id: int | None = None) -> list[SourceFile]:
    """列出项目下已归档的底稿文件。"""
    ledger_ids = [
        link.ledger_id
        for link in db.query(ProjectLedger).filter(ProjectLedger.project_id == project_id).all()
    ]
    if ledger_id is not None:
        if ledger_id not in ledger_ids:
            return []
        ledger_ids = [ledger_id]

    if not ledger_ids:
        return []

    files = (
        db.query(SourceFile)
        .outerjoin(ImportJob, SourceFile.import_job_id == ImportJob.id)
        .filter(
            (SourceFile.ledger_id.in_(ledger_ids)) | (ImportJob.ledger_id.in_(ledger_ids)),
        )
        .order_by(SourceFile.id.desc())
        .limit(500)
        .all()
    )
    return [item for item in files if load_archive_metadata(item)]
