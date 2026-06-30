import io
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes_imports import _import_reports
from app.db.models import AccountingEntry, EntryTag
from app.db.session import Base, get_db
from app.main import app
from app.models.ledger import Ledger
from app.models.team import Team


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
        team = Team(name="序时簿导入测试团队")
        db.add(team)
        db.flush()
        ledger = Ledger(name="序时簿导入测试账簿", team_id=team.id)
        db.add(ledger)
        db.commit()
        return ledger.id
    finally:
        db.close()


def test_audit_day_book_csv_import_creates_entries_tags_and_report(client):
    test_client, TestingSessionLocal = client
    ledger_id = _seed_ledger(TestingSessionLocal)
    create_response = test_client.post(
        "/api/import-jobs",
        json={
            "organization_name": "序时簿导入测试企业",
            "industry": "manufacturing",
            "fiscal_year": 2026,
            "source_type": "audit_day_book",
            "ledger_id": ledger_id,
        },
        headers=test_client._auth_headers,
    )
    assert create_response.status_code == 200
    job_id = create_response.json()["id"]

    csv_text = "\n".join([
        "凭证号,日期,摘要,科目编码,科目名称,借方,贷方,对方单位",
        "记-001,2026-01-03,收到客户货款,1002,银行存款,12000,0,客户A",
        "记-001,2026-01-03,冲减应收账款,1122,应收账款,0,12000,客户A",
    ])
    upload_response = test_client.post(
        f"/api/import-jobs/{job_id}/files",
        files={"file": ("audit-day-book.csv", io.BytesIO(csv_text.encode("utf-8-sig")), "text/csv")},
    )
    assert upload_response.status_code == 200
    assert upload_response.json()["file_type"] == "csv"

    process_response = test_client.post(f"/api/import-jobs/{job_id}/process/sync")

    assert process_response.status_code == 200
    payload = process_response.json()
    assert payload["job"]["status"] == "completed"
    assert payload["report"]["total_entries"] > 0
    assert payload["report"]["day_book_report"]["completeness_score"] > 0

    report_response = test_client.get(f"/api/import-jobs/{job_id}/report")
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["total_entries"] > 0
    assert report["day_book_report"]["completeness_score"] > 0

    db = TestingSessionLocal()
    try:
        entries = db.query(AccountingEntry).filter(AccountingEntry.import_job_id == job_id).all()
        assert len(entries) > 0
        assert {entry.account_name for entry in entries} == {"银行存款", "应收账款"}
    finally:
        db.close()
