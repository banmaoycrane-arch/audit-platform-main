import io
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes_imports import _import_reports
from app.db.models import AccountingEntry, SourceFile
from app.db.session import Base, get_db
from app.main import app
from app.models.ledger import Ledger
from app.models.team import Team
from app.services.tagging_service import suggest_voucher_type


from tests.conftest import register_auth_headers


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
    monkeypatch.setattr("app.services.import_service.safe_vector_store", lambda: None)
    monkeypatch.setattr("app.services.risk_case_library.safe_vector_store", lambda: None)
    monkeypatch.setattr("app.services.risk_rule_service.safe_vector_store", lambda: None)
    _import_reports.clear()
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            test_client._auth_headers = register_auth_headers(test_client)
            yield test_client, TestingSessionLocal
    finally:
        app.dependency_overrides.clear()
        _import_reports.clear()
        Base.metadata.drop_all(bind=engine)


def _seed_ledger(TestingSessionLocal) -> int:
    db = TestingSessionLocal()
    try:
        team = Team(name="自适应导入验收团队")
        db.add(team)
        db.flush()
        ledger = Ledger(name="自适应导入验收账簿", team_id=team.id)
        db.add(ledger)
        db.commit()
        return ledger.id
    finally:
        db.close()


def _create_job(test_client: TestClient, TestingSessionLocal) -> int:
    ledger_id = _seed_ledger(TestingSessionLocal)
    response = test_client.post(
        "/api/import-jobs",
        json={
            "organization_name": "自适应导入验收企业",
            "industry": "manufacturing",
            "fiscal_year": 2026,
            "ledger_id": ledger_id,
        },
        headers=test_client._auth_headers,
    )
    assert response.status_code == 200
    return response.json()["id"]


def _upload_csv(test_client: TestClient, job_id: int, filename: str, csv_text: str) -> None:
    response = test_client.post(
        f"/api/import-jobs/{job_id}/files",
        files={"file": (filename, io.BytesIO(csv_text.encode("utf-8-sig")), "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["file_type"] == "csv"


def test_standard_csv_import_creates_entries_and_report(client):
    test_client, TestingSessionLocal = client
    job_id = _create_job(test_client, TestingSessionLocal)
    csv_text = "\n".join([
        "voucher_no,voucher_date,summary,account_code,account_name,debit_amount,credit_amount,counterparty",
        "银-001,2026-01-05,收到客户银行回款,1002,银行存款,10000,0,客户A",
        "银-001,2026-01-05,确认客户应收款收回,1122,应收账款,0,10000,客户A",
    ])
    _upload_csv(test_client, job_id, "standard.csv", csv_text)

    process_response = test_client.post(f"/api/import-jobs/{job_id}/process/sync")

    assert process_response.status_code == 200
    payload = process_response.json()
    assert payload["job"]["status"] == "completed"
    assert payload["report"]["total_entries"] == 2
    assert payload["report"]["quality"]["overall_score"] > 0

    report_response = test_client.get(f"/api/import-jobs/{job_id}/report")
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["total_entries"] == 2
    assert report["quality"]["overall_score"] > 0

    db = TestingSessionLocal()
    try:
        assert db.query(AccountingEntry).filter(AccountingEntry.import_job_id == job_id).count() == 2
    finally:
        db.close()


def test_custom_header_csv_import_creates_entries(client):
    test_client, TestingSessionLocal = client
    job_id = _create_job(test_client, TestingSessionLocal)
    csv_text = "\n".join([
        "凭证号,日期,摘要,科目编码,科目名称,借方,贷方,对方单位",
        "记-002,2026-02-10,支付供应商货款,2202,应付账款,5000,0,供应商A",
        "记-002,2026-02-10,银行转账付款,1002,银行存款,0,5000,供应商A",
    ])
    _upload_csv(test_client, job_id, "custom-header.csv", csv_text)

    process_response = test_client.post(f"/api/import-jobs/{job_id}/process/sync")

    assert process_response.status_code == 200
    payload = process_response.json()
    assert payload["report"]["total_entries"] == 2
    assert payload["report"]["file_summary"][0]["success"] is True

    db = TestingSessionLocal()
    try:
        entries = db.query(AccountingEntry).filter(AccountingEntry.import_job_id == job_id).all()
        assert len(entries) == 2
        assert {entry.account_name for entry in entries} == {"应付账款", "银行存款"}
    finally:
        db.close()


def test_source_file_upload_parse_returns_feedback_fields(client):
    test_client, TestingSessionLocal = client
    job_id = _create_job(test_client, TestingSessionLocal)
    source_text = "发票号码：ABCD123456 开票日期：2026-06-10 购买方：客户A 销售方：供应商B 价税合计（大写） 1200.00"

    upload_response = test_client.post(
        f"/api/import-jobs/{job_id}/files",
        files={"file": ("发票.txt", io.BytesIO(source_text.encode("utf-8")), "text/plain")},
    )

    assert upload_response.status_code == 200
    uploaded_file = upload_response.json()
    assert uploaded_file["upload_status"] == "uploaded"
    assert uploaded_file["parse_status"] == "pending"

    parse_response = test_client.post(f"/api/import-jobs/{job_id}/files/{uploaded_file['id']}/parse")

    assert parse_response.status_code == 200
    parsed_file = parse_response.json()
    assert parsed_file["upload_status"] == "uploaded"
    assert parsed_file["parse_status"] == "text_extracted"
    assert parsed_file["parse_feedback"]["document_type"] in {"invoice", "source_file", "unknown"}
    assert parsed_file["parse_feedback"].get("text_length", 0) > 0

    list_response = test_client.get(f"/api/import-jobs/{job_id}/files")
    assert list_response.status_code == 200
    assert list_response.json()[0]["parse_feedback"]["summary"]

    db = TestingSessionLocal()
    try:
        source_file = db.get(SourceFile, uploaded_file["id"])
        assert source_file.text_extract_status == "text_extracted"
    finally:
        db.close()


def test_voucher_type_recommendation_for_bank_entry():
    entry = SimpleNamespace(summary="收到银行回单并通过网银收款", account_name="银行存款", debit_amount=1000, credit_amount=0)

    voucher_type, confidence = suggest_voucher_type(entry)

    assert voucher_type == "银"
    assert confidence >= 0.3
