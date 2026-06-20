import io
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes_imports import _day_book_reports, _import_reports
from app.db.models import AccountingEntry, ImportJob
from app.db.session import Base, get_db
from app.main import app


@pytest.fixture
def client(monkeypatch, tmp_path):
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

    monkeypatch.setattr("app.storage.local_storage.get_settings", lambda: SimpleNamespace(upload_dir=str(tmp_path)))
    monkeypatch.setattr("app.services.audit_day_book_service.safe_vector_store", lambda: None)
    monkeypatch.setattr("app.services.import_service.safe_vector_store", lambda: None)
    monkeypatch.setattr("app.services.risk_case_library.safe_vector_store", lambda: None)
    monkeypatch.setattr("app.services.risk_rule_service.safe_vector_store", lambda: None)
    _import_reports.clear()
    _day_book_reports.clear()
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client, TestingSessionLocal
    finally:
        app.dependency_overrides.clear()
        _import_reports.clear()
        _day_book_reports.clear()
        Base.metadata.drop_all(bind=engine)


def _create_day_book_job(test_client: TestClient) -> int:
    response = test_client.post(
        "/api/import-jobs",
        json={
            "organization_name": "序时簿导入测试企业",
            "industry": "manufacturing",
            "fiscal_year": 2026,
            "source_type": "audit_day_book",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source_type"] == "audit_day_book"
    return payload["id"]


def _upload_day_book_csv(test_client: TestClient, job_id: int, csv_text: str) -> None:
    response = test_client.post(
        f"/api/import-jobs/{job_id}/files",
        files={"file": ("audit-day-book.csv", io.BytesIO(csv_text.encode("utf-8-sig")), "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["file_type"] == "csv"


def test_create_audit_day_book_job_stores_source_type(client):
    test_client, TestingSessionLocal = client
    job_id = _create_day_book_job(test_client)

    db = TestingSessionLocal()
    try:
        job = db.get(ImportJob, job_id)
        assert job is not None
        assert job.source_type == "audit_day_book"
    finally:
        db.close()


def test_audit_day_book_groups_entries_and_returns_report(client):
    test_client, TestingSessionLocal = client
    job_id = _create_day_book_job(test_client)
    csv_text = "\n".join([
        "凭证号,日期,摘要,科目编码,科目名称,借方,贷方,对方单位",
        "记-001,2026-01-03,收到客户货款,1002,银行存款,12000,0,客户A",
        "记-001,2026-01-03,冲减应收账款,1122,应收账款,0,12000,客户A",
        "记-003,2026-01-05,支付服务费,6602,管理费用,500,0,供应商B",
        "记-003,2026-01-05,银行付款,1002,银行存款,0,500,供应商B",
    ])
    _upload_day_book_csv(test_client, job_id, csv_text)

    process_response = test_client.post(f"/api/import-jobs/{job_id}/process/sync")
    assert process_response.status_code == 200
    assert process_response.json()["job"]["status"] == "completed"

    report_response = test_client.get(f"/api/import-jobs/{job_id}/day-book-report")
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["total_vouchers"] == 2
    assert report["total_entries"] == 4
    assert report["skip_count"] == 1
    assert report["missing_voucher_nos"] == ["记-002"]
    assert report["unbalanced_count"] == 0
    assert report["completeness_score"] == 98.0

    db = TestingSessionLocal()
    try:
        entries = db.query(AccountingEntry).filter(AccountingEntry.import_job_id == job_id).all()
        assert len(entries) == 4
        voucher_001_lines = [entry.entry_line_no for entry in entries if entry.voucher_no == "记-001"]
        assert voucher_001_lines == [1, 2]
    finally:
        db.close()


def test_audit_day_book_marks_unbalanced_vouchers(client):
    test_client, _ = client
    job_id = _create_day_book_job(test_client)
    csv_text = "\n".join([
        "凭证号,日期,摘要,科目编码,科目名称,借方,贷方,对方单位",
        "记-001,2026-01-03,收到客户货款,1002,银行存款,12000,0,客户A",
        "记-001,2026-01-03,冲减应收账款,1122,应收账款,0,11000,客户A",
    ])
    _upload_day_book_csv(test_client, job_id, csv_text)

    process_response = test_client.post(f"/api/import-jobs/{job_id}/process/sync")
    assert process_response.status_code == 200

    report_response = test_client.get(f"/api/import-jobs/{job_id}/day-book-report")
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["unbalanced_count"] == 1
    assert report["unbalanced_vouchers"][0]["voucher_no"] == "记-001"
    assert report["unbalanced_vouchers"][0]["difference"] == "1000.00"
    assert report["completeness_score"] == 95.0


def test_day_book_report_rejects_voucher_import_job(client):
    test_client, _ = client
    response = test_client.post(
        "/api/import-jobs",
        json={"organization_name": "普通凭证导入测试企业"},
    )
    assert response.status_code == 200
    job_id = response.json()["id"]

    report_response = test_client.get(f"/api/import-jobs/{job_id}/day-book-report")
    assert report_response.status_code == 400
    assert report_response.json()["detail"] == "该任务不是序时簿导入任务"
