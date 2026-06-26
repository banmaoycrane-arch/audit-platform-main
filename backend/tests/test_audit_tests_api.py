from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import (
    AccountingEntry,
    AuditFinding,
    AuditFindingReviewAction,
    AuditReport,
    ImportJob,
    Organization,
    SourceFile,
)
from app.db.session import Base, get_db
from app.main import app
from app.services.audit_test_service import audit_test_service
from app.services.ledger_service import ledger_service


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    audit_test_service.clear_findings()
    ledger_service.contract_ledger.clear()
    ledger_service.invoice_ledger.clear()
    ledger_service.inventory_ledger.clear()
    ledger_service.bank_statement_ledger.clear()
    try:
        with TestClient(app) as test_client:
            yield test_client, TestingSessionLocal
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def seed_audit_job(TestingSessionLocal, filename: str = "采购发票.pdf"):
    db = TestingSessionLocal()
    try:
        organization = Organization(name="审计测试企业", fiscal_year=2026)
        db.add(organization)
        db.flush()
        job = ImportJob(organization_id=organization.id, status="completed", entry_count=1, file_count=1)
        db.add(job)
        db.flush()
        db.add(
            SourceFile(
                organization_id=organization.id,
                import_job_id=job.id,
                filename=filename,
                file_type="invoice",
                storage_path=f"/tmp/{filename}",
                text_extract_status="completed",
            )
        )
        db.add(
            AccountingEntry(
                organization_id=organization.id,
                import_job_id=job.id,
                voucher_no="记-001",
                voucher_date=date(2026, 1, 10),
                summary="采购材料",
                account_code="1403",
                account_name="原材料",
                debit_amount=Decimal("1000.00"),
                credit_amount=Decimal("0.00"),
                counterparty="供应商A",
            )
        )
        db.commit()
        return job.id
    finally:
        db.close()


def test_run_audit_tests_generates_report_and_findings(client):
    test_client, TestingSessionLocal = client
    job_id = seed_audit_job(TestingSessionLocal)

    run_response = test_client.post(f"/api/audit-tests/{job_id}/run")
    assert run_response.status_code == 200
    report = run_response.json()
    assert report["scope"] == "全量审计"
    assert "audit_scope" in report
    assert report["audit_scope"]["audit_scope_type"] is None
    assert "summary" in report
    assert "findings" in report
    assert report["summary"]["total_findings"] == len(report["findings"])

    db = TestingSessionLocal()
    try:
        persisted_report = db.query(AuditReport).filter(AuditReport.import_job_id == job_id).first()
    finally:
        db.close()
    assert persisted_report is not None
    assert persisted_report.report_payload["scope"] == "全量审计"
    assert "audit_scope" in persisted_report.report_payload

    report_response = test_client.get(f"/api/audit-tests/{job_id}/report")
    assert report_response.status_code == 200
    assert report_response.json()["summary"]["total_findings"] == report["summary"]["total_findings"]

    findings_response = test_client.get(f"/api/audit-tests/{job_id}/findings")
    assert findings_response.status_code == 200
    assert isinstance(findings_response.json(), list)


def test_run_audit_tests_uses_saved_scope_metadata(client):
    test_client, TestingSessionLocal = client
    job_id = seed_audit_job(TestingSessionLocal)

    db = TestingSessionLocal()
    try:
        job = db.get(ImportJob, job_id)
        job.audit_scope_type = "by_account"
        job.audit_account_codes = ["1403"]
        db.commit()
    finally:
        db.close()

    run_response = test_client.post(f"/api/audit-tests/{job_id}/run")
    assert run_response.status_code == 200
    report = run_response.json()
    assert report["scope"] == "按科目审计: 1403"
    assert report["audit_scope"]["audit_scope_type"] == "by_account"
    assert report["audit_scope"]["audit_account_codes"] == ["1403"]


def test_get_report_before_run_returns_404(client):
    test_client, TestingSessionLocal = client
    job_id = seed_audit_job(TestingSessionLocal)

    response = test_client.get(f"/api/audit-tests/{job_id}/report")
    assert response.status_code == 404
    assert "请先执行测试" in response.json()["detail"]


def test_audit_reports_are_isolated_by_import_job_id(client):
    test_client, TestingSessionLocal = client
    first_job_id = seed_audit_job(TestingSessionLocal, filename="第一任务发票.pdf")
    second_job_id = seed_audit_job(TestingSessionLocal, filename="第二任务发票.pdf")

    first_run = test_client.post(f"/api/audit-tests/{first_job_id}/run")
    assert first_run.status_code == 200
    second_run = test_client.post(f"/api/audit-tests/{second_job_id}/run")
    assert second_run.status_code == 200

    first_report = test_client.get(f"/api/audit-tests/{first_job_id}/report")
    second_report = test_client.get(f"/api/audit-tests/{second_job_id}/report")

    assert first_report.status_code == 200
    assert second_report.status_code == 200
    assert first_report.json()["scope"] == "全量审计"
    assert second_report.json()["scope"] == "全量审计"

    db = TestingSessionLocal()
    try:
        report_count = db.query(AuditReport).count()
        first_persisted = (
            db.query(AuditReport)
            .filter(AuditReport.import_job_id == first_job_id)
            .first()
        )
        second_persisted = (
            db.query(AuditReport)
            .filter(AuditReport.import_job_id == second_job_id)
            .first()
        )
    finally:
        db.close()

    assert report_count == 2
    assert first_persisted is not None
    assert second_persisted is not None
    assert first_persisted.report_payload["scope"] == "全量审计"
    assert second_persisted.report_payload["scope"] == "全量审计"


def test_run_audit_tests_unknown_job_returns_404(client):
    test_client, _ = client

    response = test_client.post("/api/audit-tests/999/run")
    assert response.status_code == 404
    assert response.json()["detail"] == "导入任务不存在"


def test_run_audit_tests_persists_findings(client):
    test_client, TestingSessionLocal = client
    job_id = seed_audit_job(TestingSessionLocal)

    run_response = test_client.post(f"/api/audit-tests/{job_id}/run")
    assert run_response.status_code == 200
    payload = run_response.json()

    db = TestingSessionLocal()
    try:
        persisted = db.query(AuditFinding).filter(AuditFinding.job_id == job_id).all()
    finally:
        db.close()
    assert len(persisted) == len(payload["findings"])


def test_rerun_audit_tests_replaces_old_findings(client):
    test_client, TestingSessionLocal = client
    job_id = seed_audit_job(TestingSessionLocal)

    test_client.post(f"/api/audit-tests/{job_id}/run")
    db = TestingSessionLocal()
    try:
        first_count = db.query(AuditFinding).filter(AuditFinding.job_id == job_id).count()
    finally:
        db.close()

    test_client.post(f"/api/audit-tests/{job_id}/run")
    db = TestingSessionLocal()
    try:
        second = db.query(AuditFinding).filter(AuditFinding.job_id == job_id).all()
    finally:
        db.close()

    # 数量不应翻倍，证明旧发现被覆盖
    assert len(second) == first_count


def test_review_audit_finding_records_action(client):
    test_client, TestingSessionLocal = client
    job_id = seed_audit_job(TestingSessionLocal)

    test_client.post(f"/api/audit-tests/{job_id}/run")
    db = TestingSessionLocal()
    try:
        finding = db.query(AuditFinding).filter(AuditFinding.job_id == job_id).first()
    finally:
        db.close()

    if not finding:
        pytest.skip("当前样例数据未生成审计发现")

    response = test_client.patch(
        f"/api/audit-tests/findings/{finding.id}/review",
        json={"action": "confirmed", "comment": "已经核实"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"

    db = TestingSessionLocal()
    try:
        updated = db.get(AuditFinding, finding.id)
        actions = (
            db.query(AuditFindingReviewAction)
            .filter(AuditFindingReviewAction.finding_id == finding.id)
            .all()
        )
    finally:
        db.close()

    assert updated is not None
    assert updated.status == "confirmed"
    assert len(actions) == 1
    assert actions[0].action == "confirmed"
    assert actions[0].comment == "已经核实"


def test_review_unknown_finding_returns_404(client):
    test_client, _ = client

    response = test_client.patch(
        "/api/audit-tests/findings/9999/review",
        json={"action": "confirmed"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "审计发现不存在"
