"""审计报告导出服务。"""
from __future__ import annotations

import io
import json
from typing import Any

from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.db.models import AuditFinding, AuditReport

SUPPORTED_FORMATS = {"xlsx", "json"}

OVERVIEW_FIELDS = [
    ("test_date", "测试时间"),
    ("period", "审计期间"),
    ("scope", "审计范围"),
    ("total_transactions", "交易总数"),
    ("tested_transactions", "已测试交易数"),
]

FINDING_COLUMNS = [
    ("finding_type", "发现类型"),
    ("severity", "严重程度"),
    ("business_type", "业务类型"),
    ("finding_title", "发现标题"),
    ("finding_description", "发现描述"),
    ("audit_procedure", "审计程序"),
    ("audit_conclusion", "审计结论"),
    ("risk_statement", "风险表述"),
    ("recommendation", "建议措施"),
    ("status", "复核状态"),
]


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


def build_report_payload(
    db: Session,
    job_id: int,
    memory_reports: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if memory_reports and job_id in memory_reports:
        return memory_reports[job_id]

    report = db.query(AuditReport).filter(AuditReport.import_job_id == job_id).first()
    if report:
        return dict(report.report_payload or {})

    findings = db.query(AuditFinding).filter(AuditFinding.job_id == job_id).all()
    findings_payload = [_finding_to_dict(item) for item in findings]
    summary = {
        "total_findings": len(findings_payload),
        "high_severity": sum(1 for f in findings_payload if f.get("severity") == "high"),
        "medium_severity": sum(1 for f in findings_payload if f.get("severity") == "medium"),
        "low_severity": sum(1 for f in findings_payload if f.get("severity") == "low"),
    }
    return {
        "test_date": "",
        "period": "",
        "scope": f"导入任务 {job_id}",
        "total_transactions": 0,
        "tested_transactions": 0,
        "summary": summary,
        "findings": findings_payload,
    }


def report_to_xlsx(report: dict[str, Any]) -> bytes:
    wb = Workbook()

    ws_overview = wb.active
    ws_overview.title = "概览"
    ws_overview.append(["项目", "值"])
    for key, label in OVERVIEW_FIELDS:
        ws_overview.append([label, report.get(key, "")])

    summary = report.get("summary", {}) or {}
    ws_overview.append([])
    ws_overview.append(["发现汇总", ""])
    ws_overview.append(["发现总数", summary.get("total_findings", 0)])
    ws_overview.append(["高风险", summary.get("high_severity", 0)])
    ws_overview.append(["中风险", summary.get("medium_severity", 0)])
    ws_overview.append(["低风险", summary.get("low_severity", 0)])

    by_type = summary.get("by_type", {}) or {}
    if by_type:
        ws_overview.append([])
        ws_overview.append(["按类型分布", ""])
        for type_name, count in by_type.items():
            if count:
                ws_overview.append([type_name, count])

    ws_findings = wb.create_sheet("审计发现")
    ws_findings.append([label for _, label in FINDING_COLUMNS])
    for finding in report.get("findings", []) or []:
        row = []
        for key, _ in FINDING_COLUMNS:
            value = finding.get(key, "")
            if isinstance(value, (list, dict)):
                value = json.dumps(value, ensure_ascii=False)
            row.append("" if value is None else value)
        ws_findings.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def report_to_json(report: dict[str, Any]) -> bytes:
    return json.dumps(report, ensure_ascii=False, indent=2, default=str).encode("utf-8")
