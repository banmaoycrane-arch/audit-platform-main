from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import AccountingPeriod, ImportJob, Organization
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


def seed_period(TestingSessionLocal) -> int:
    db = TestingSessionLocal()
    try:
        org = Organization(name="范围测试企业", fiscal_year=2026)
        db.add(org)
        db.flush()
        period = AccountingPeriod(
            organization_id=org.id,
            period_code="2026-01",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )
        db.add(period)
        db.commit()
        return period.id
    finally:
        db.close()


def test_create_import_job_with_audit_scope(client):
    test_client, TestingSessionLocal = client
    period_id = seed_period(TestingSessionLocal)

    response = test_client.post(
        "/api/import-jobs",
        json={
            "organization_name": "审计企业",
            "source_type": "voucher_import",
            "audit_scope_type": "by_period",
            "audit_period_id": period_id,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["audit_scope_type"] == "by_period"
    assert payload["audit_period_id"] == period_id


def test_put_audit_scope_updates_job(client):
    test_client, TestingSessionLocal = client
    period_id = seed_period(TestingSessionLocal)

    create_response = test_client.post(
        "/api/import-jobs",
        json={"organization_name": "审计企业"},
    )
    job_id = create_response.json()["id"]

    update_response = test_client.put(
        f"/api/import-jobs/{job_id}/audit-scope",
        json={
            "audit_scope_type": "by_account",
            "audit_account_codes": ["1001", "1002"],
        },
    )
    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["audit_scope_type"] == "by_account"
    assert payload["audit_account_codes"] == ["1001", "1002"]

    db = TestingSessionLocal()
    try:
        job = db.get(ImportJob, job_id)
    finally:
        db.close()
    assert job is not None
    assert job.audit_scope_type == "by_account"
    assert job.audit_account_codes == ["1001", "1002"]


def test_put_audit_scope_requires_accounts_for_by_account(client):
    test_client, _ = client
    create_response = test_client.post(
        "/api/import-jobs",
        json={"organization_name": "审计企业"},
    )
    job_id = create_response.json()["id"]

    response = test_client.put(
        f"/api/import-jobs/{job_id}/audit-scope",
        json={"audit_scope_type": "by_account", "audit_account_codes": []},
    )
    assert response.status_code == 400


def test_put_audit_scope_requires_period_for_by_period(client):
    test_client, _ = client
    create_response = test_client.post(
        "/api/import-jobs",
        json={"organization_name": "审计企业"},
    )
    job_id = create_response.json()["id"]

    response = test_client.put(
        f"/api/import-jobs/{job_id}/audit-scope",
        json={"audit_scope_type": "by_period"},
    )
    assert response.status_code == 400


def test_put_audit_scope_unknown_job_returns_404(client):
    test_client, _ = client
    response = test_client.put(
        "/api/import-jobs/9999/audit-scope",
        json={"audit_scope_type": "all"},
    )
    assert response.status_code == 404
