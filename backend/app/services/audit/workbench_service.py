"""内控待办工作台：聚合内控缺陷、维度待办、风险提醒。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditFinding, AuditRisk, ImportJob
from app.services.audit.structured_import_service import build_dimension_pending_queue

DIMENSION_QUEUE_TYPES = {
    "non_standardized",
    "missing_in_master",
    "requires_llm",
    "unknown_category",
}

SEVERITY_ORDER = {"blocking": 0, "warning": 1, "info": 2}
SOURCE_LABELS = {
    "internal_control": "内控规则",
    "risk": "风险提醒",
    "dimension": "维度待办",
}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _map_risk_severity(risk_level: str) -> str:
    lowered = (risk_level or "").lower()
    if lowered in {"high", "critical", "severe"}:
        return "warning"
    if lowered in {"blocking", "block"}:
        return "blocking"
    return "info"


def _map_dimension_severity(priority: str) -> str:
    if priority == "high":
        return "warning"
    if priority == "medium":
        return "info"
    return "info"


def _map_finding_severity(severity: str) -> str:
    lowered = (severity or "").lower()
    if lowered in {"high", "critical", "blocking"}:
        return "warning"
    if lowered == "blocking":
        return "blocking"
    return "info"


def _internal_control_items(
    db: Session,
    *,
    ledger_id: int,
    status: str | None,
    job_id: int | None,
) -> list[dict[str, Any]]:
    query = db.query(AuditFinding).filter(
        AuditFinding.ledger_id == ledger_id,
        AuditFinding.finding_type == "internal_control",
    )
    if job_id is not None:
        query = query.filter(AuditFinding.job_id == job_id)
    if status and status != "all":
        query = query.filter(AuditFinding.status == status)
    else:
        query = query.filter(AuditFinding.status == "pending")
    findings = query.order_by(AuditFinding.created_at.desc()).limit(200).all()
    items: list[dict[str, Any]] = []
    for finding in findings:
        meta = finding.finding_metadata or {}
        items.append(
            {
                "id": f"internal_control:{finding.id}",
                "source": "internal_control",
                "source_label": SOURCE_LABELS["internal_control"],
                "severity": _map_finding_severity(finding.severity),
                "category": "master_data",
                "title": finding.finding_title,
                "description": finding.finding_description or "",
                "status": finding.status,
                "ledger_id": finding.ledger_id,
                "job_id": finding.job_id,
                "related_finding_id": finding.id,
                "related_entry_ids": list(finding.related_entries or []),
                "related_source_file_ids": list(finding.related_files or []),
                "metadata": meta,
                "suggested_path": f"/ledger/vouchers/step/4?jobId={finding.job_id}" if finding.job_id else "/ledger/control-defects",
                "suggested_action": "在 Step4 维度注册表或本页复核关闭",
                "created_at": _iso(finding.created_at),
            }
        )
    return items


def _risk_items(
    db: Session,
    *,
    ledger_id: int,
    status: str | None,
    job_id: int | None,
) -> list[dict[str, Any]]:
    query = db.query(AuditRisk).filter(AuditRisk.ledger_id == ledger_id)
    if job_id is not None:
        query = query.filter(AuditRisk.import_job_id == job_id)
    if status and status != "all":
        query = query.filter(AuditRisk.status == status)
    else:
        query = query.filter(AuditRisk.status == "pending_review")
    risks = query.order_by(AuditRisk.created_at.desc()).limit(200).all()
    items: list[dict[str, Any]] = []
    for risk in risks:
        items.append(
            {
                "id": f"risk:{risk.id}",
                "source": "risk",
                "source_label": SOURCE_LABELS["risk"],
                "severity": _map_risk_severity(risk.risk_level),
                "category": "reconciliation",
                "title": risk.title,
                "description": risk.description or "",
                "status": risk.status,
                "ledger_id": risk.ledger_id,
                "job_id": risk.import_job_id,
                "related_finding_id": None,
                "related_entry_ids": [],
                "related_source_file_ids": [],
                "metadata": {
                    "risk_type": risk.risk_type,
                    "risk_level": risk.risk_level,
                    "confidence": risk.confidence,
                },
                "suggested_path": f"/risks?jobId={risk.import_job_id}",
                "suggested_action": "在风险列表复核确认或标记误报",
                "created_at": _iso(risk.created_at),
            }
        )
    return items


def _dimension_items(
    db: Session,
    *,
    ledger_id: int,
    job_id: int | None,
    max_jobs: int = 12,
) -> list[dict[str, Any]]:
    job_query = (
        db.query(ImportJob)
        .filter(ImportJob.ledger_id == ledger_id)
        .filter(ImportJob.source_type != "evidence_inbox")
        .order_by(ImportJob.id.desc())
    )
    if job_id is not None:
        job_query = job_query.filter(ImportJob.id == job_id)
    jobs = job_query.limit(max_jobs).all()

    items: list[dict[str, Any]] = []
    for job in jobs:
        queue = build_dimension_pending_queue(db, job.id)
        for index, row in enumerate(queue.get("items") or []):
            queue_type = str(row.get("queue_type") or "")
            if queue_type not in DIMENSION_QUEUE_TYPES:
                continue
            items.append(
                {
                    "id": f"dimension:{job.id}:{queue_type}:{index}",
                    "source": "dimension",
                    "source_label": SOURCE_LABELS["dimension"],
                    "severity": _map_dimension_severity(str(row.get("priority") or "medium")),
                    "category": "master_data",
                    "title": str(row.get("message") or "维度待办"),
                    "description": _dimension_description(row),
                    "status": "open",
                    "ledger_id": ledger_id,
                    "job_id": job.id,
                    "related_finding_id": row.get("finding_id"),
                    "related_entry_ids": [row["staging_id"]] if row.get("staging_id") else [],
                    "related_source_file_ids": [],
                    "metadata": row,
                    "suggested_path": f"/ledger/vouchers/step/4?jobId={job.id}",
                    "suggested_action": "在 Step4 处理维度映射或补全主数据",
                    "created_at": None,
                }
            )
    return items


def _dimension_description(row: dict[str, Any]) -> str:
    parts: list[str] = []
    if row.get("account_code"):
        parts.append(f"科目 {row['account_code']}")
    if row.get("category_code"):
        parts.append(f"维度 {row['category_code']}")
    if row.get("tag_value"):
        parts.append(f"值 {row['tag_value']}")
    if row.get("voucher_no"):
        parts.append(f"凭证 {row['voucher_no']}")
    if row.get("line_count"):
        parts.append(f"{row['line_count']} 行")
    return " · ".join(parts) if parts else str(row.get("queue_type") or "")


def build_workbench_queue(
    db: Session,
    *,
    ledger_id: int,
    status: str | None = None,
    source: str | None = None,
    job_id: int | None = None,
    limit: int = 300,
) -> dict[str, Any]:
    """聚合账簿级待办队列（只读合并，不强制阻塞）。"""
    items: list[dict[str, Any]] = []
    if source in (None, "", "all", "internal_control"):
        items.extend(_internal_control_items(db, ledger_id=ledger_id, status=status, job_id=job_id))
    if source in (None, "", "all", "risk"):
        items.extend(_risk_items(db, ledger_id=ledger_id, status=status, job_id=job_id))
    if source in (None, "", "all", "dimension"):
        if status in (None, "", "pending", "open", "all"):
            items.extend(_dimension_items(db, ledger_id=ledger_id, job_id=job_id))

    items.sort(
        key=lambda row: (
            SEVERITY_ORDER.get(str(row.get("severity")), 9),
            row.get("created_at") or "",
            str(row.get("id")),
        )
    )
    if limit > 0:
        items = items[:limit]

    summary = {
        "total": len(items),
        "blocking": sum(1 for item in items if item.get("severity") == "blocking"),
        "warning": sum(1 for item in items if item.get("severity") == "warning"),
        "info": sum(1 for item in items if item.get("severity") == "info"),
        "by_source": {
            "internal_control": sum(1 for item in items if item.get("source") == "internal_control"),
            "dimension": sum(1 for item in items if item.get("source") == "dimension"),
            "risk": sum(1 for item in items if item.get("source") == "risk"),
        },
    }
    return {
        "ledger_id": ledger_id,
        "summary": summary,
        "items": items,
    }
