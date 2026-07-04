import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import AuditFinding, ImportJob, Organization
from app.db.session import Base
from app.services.audit.audit_report_service import (
    build_report_payload,
    report_to_json,
    report_to_xlsx,
)


def _seed_job_with_findings(TestingSessionLocal):
    db = TestingSessionLocal()
    try:
        org = Organization(name="审计报告服务测试企业", fiscal_year=2026)
        db.add(org)
        db.flush()
        job = ImportJob(organization_id=org.id, status="completed", entry_count=1, file_count=1)
        db.add(job)
        db.flush()
        db.add(
            AuditFinding(
                job_id=job.id,
                finding_uuid="uuid-service-1",
                finding_type="ghost_invoice",
                severity="high",
                business_type="purchase",
                finding_title="幽灵发票",
                finding_description="发票缺乏真实业务支撑",
                audit_procedure="逆查程序",
                audit_conclusion="无法证实其真实业务背景",
                risk_statement="可能存在虚开发票",
                recommendation="补充入库单与合同",
                related_entries=["entry-1"],
                related_files=["发票A.pdf"],
                finding_metadata={},
                status="pending",
            )
        )
        db.commit()
        return job.id
    finally:
        db.close()


def test_audit_report_service_builds_payload_and_exports_bytes():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    job_id = _seed_job_with_findings(TestingSessionLocal)

    db = TestingSessionLocal()
    try:
        report = build_report_payload(db, job_id, memory_reports={})
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

    assert report["scope"] == f"导入任务 {job_id}"
    assert report["summary"]["total_findings"] == 1
    assert report["summary"]["high_severity"] == 1
    assert len(report["findings"]) == 1
    assert report["findings"][0]["finding_title"] == "幽灵发票"

    json_body = report_to_json(report)
    assert isinstance(json_body, bytes)
    json_payload = json.loads(json_body.decode("utf-8"))
    assert "findings" in json_payload
    assert json_payload["findings"][0]["finding_type"] == "ghost_invoice"

    xlsx_body = report_to_xlsx(report)
    assert isinstance(xlsx_body, bytes)
    assert xlsx_body[:2] == b"PK"
    assert len(xlsx_body) > 100
