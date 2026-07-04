from datetime import date

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
            test_client._SessionLocal = TestingSessionLocal  # type: ignore[attr-defined]
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _seed_entry(db) -> int:
    org = Organization(name="复核测试企业")
    db.add(org)
    db.commit()
    db.refresh(org)
    job = ImportJob(organization_id=org.id, status="completed")
    db.add(job)
    db.commit()
    db.refresh(job)
    entry = AccountingEntry(
        organization_id=org.id,
        import_job_id=job.id,
        voucher_no="V100",
        voucher_date=date(2026, 6, 1),
        summary="原摘要",
        account_code="1002",
        account_name="银行存款",
        debit_amount=100,
        credit_amount=0,
        review_status="draft",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry.id


def test_update_entry_review_status(client: TestClient):
    db = client._SessionLocal()  # type: ignore[attr-defined]
    try:
        entry_id = _seed_entry(db)
    finally:
        db.close()

    response = client.patch(f"/api/entries/{entry_id}/review", json={"review_status": "verified"})
    assert response.status_code == 200
    data = response.json()
    assert data["review_status"] == "verified"


def test_batch_update_entry_review_status(client: TestClient):
    db = client._SessionLocal()  # type: ignore[attr-defined]
    try:
        entry_id = _seed_entry(db)
    finally:
        db.close()

    response = client.post("/api/entries/batch-review", json={"entry_ids": [entry_id], "review_status": "ready"})
    assert response.status_code == 200
    assert response.json()["updated"] == 1

    get_resp = client.get(f"/api/entries/{entry_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["review_status"] == "ready"


def test_update_entry_fields_before_review(client: TestClient):
    db = client._SessionLocal()  # type: ignore[attr-defined]
    try:
        entry_id = _seed_entry(db)
    finally:
        db.close()

    response = client.patch(
        f"/api/entries/{entry_id}",
        json={
            "summary": "调整后摘要",
            "account_code": "6602",
            "account_name": "管理费用",
            "debit_amount": 88,
            "credit_amount": 0,
            "counterparty": "测试供应商",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "调整后摘要"
    assert data["account_code"] == "6602"
    assert data["account_name"] == "管理费用"
    assert data["debit_amount"] == "88.00"
    assert data["counterparty"] == "测试供应商"


def test_verified_entry_cannot_be_edited_directly(client: TestClient):
    db = client._SessionLocal()  # type: ignore[attr-defined]
    try:
        entry_id = _seed_entry(db)
    finally:
        db.close()

    review_response = client.patch(f"/api/entries/{entry_id}/review", json={"review_status": "verified"})
    assert review_response.status_code == 200

    edit_response = client.patch(f"/api/entries/{entry_id}", json={"summary": "不应修改"})
    assert edit_response.status_code == 400
    assert "已复核分录不能直接修改" in edit_response.json()["detail"]
