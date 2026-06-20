from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import AccountingEntry, ImportJob, Organization
from app.db.session import Base, get_db
from app.main import app


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
    try:
        with TestClient(app) as test_client:
            yield test_client, TestingSessionLocal
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _seed(TestingSessionLocal):
    db = TestingSessionLocal()
    try:
        org = Organization(name="导出测试", fiscal_year=2026)
        db.add(org)
        db.flush()
        job = ImportJob(organization_id=org.id, status="completed", entry_count=2, file_count=1)
        db.add(job)
        db.flush()
        db.add(
            AccountingEntry(
                organization_id=org.id,
                import_job_id=job.id,
                voucher_no="银-001",
                entry_line_no=1,
                voucher_date=date(2026, 1, 5),
                summary="收到 A公司 货款",
                account_code="1002",
                account_name="银行存款",
                debit_amount=Decimal("1000"),
                credit_amount=Decimal("0"),
                counterparty="A公司",
            )
        )
        db.add(
            AccountingEntry(
                organization_id=org.id,
                import_job_id=job.id,
                voucher_no="银-001",
                entry_line_no=2,
                voucher_date=date(2026, 1, 5),
                summary="确认收入",
                account_code="6001",
                account_name="主营业务收入",
                debit_amount=Decimal("0"),
                credit_amount=Decimal("1000"),
                counterparty="A公司",
            )
        )
        db.commit()
        return job.id
    finally:
        db.close()


def test_export_xlsx_returns_xlsx(client):
    test_client, TestingSessionLocal = client
    job_id = _seed(TestingSessionLocal)
    response = test_client.get(f"/api/import-jobs/{job_id}/export", params={"format": "xlsx"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "attachment" in response.headers["content-disposition"]
    assert len(response.content) > 100


def test_export_csv_contains_data(client):
    test_client, TestingSessionLocal = client
    job_id = _seed(TestingSessionLocal)
    response = test_client.get(f"/api/import-jobs/{job_id}/export", params={"format": "csv"})
    assert response.status_code == 200
    text = response.content.decode("utf-8-sig")
    assert "凭证号" in text
    assert "银-001" in text
    assert "A公司" in text


def test_export_json_contains_entries(client):
    test_client, TestingSessionLocal = client
    job_id = _seed(TestingSessionLocal)
    response = test_client.get(f"/api/import-jobs/{job_id}/export", params={"format": "json"})
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == 2
    assert payload[0]["voucher_no"] == "银-001"


def test_export_unknown_job_404(client):
    test_client, _ = client
    response = test_client.get("/api/import-jobs/9999/export", params={"format": "xlsx"})
    assert response.status_code == 404


def test_export_unknown_format_400(client):
    test_client, TestingSessionLocal = client
    job_id = _seed(TestingSessionLocal)
    response = test_client.get(f"/api/import-jobs/{job_id}/export", params={"format": "pdf"})
    assert response.status_code == 400
    assert "不支持的导出格式" in response.json()["detail"]
