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


def _seed_job(
    TestingSessionLocal,
    *,
    review_status: str = "ready",
    post_status: str = "draft",
) -> int:
    db = TestingSessionLocal()
    try:
        org = Organization(name="入账测试", fiscal_year=2026)
        db.add(org)
        db.flush()
        job = ImportJob(organization_id=org.id, status="completed", entry_count=2, file_count=1)
        db.add(job)
        db.flush()
        for line_no, account_code, account_name, debit, credit in [
            (1, "1002", "银行存款", Decimal("1000"), Decimal("0")),
            (2, "6001", "主营业务收入", Decimal("0"), Decimal("1000")),
        ]:
            db.add(
                AccountingEntry(
                    organization_id=org.id,
                    import_job_id=job.id,
                    voucher_no="银-001",
                    entry_line_no=line_no,
                    voucher_date=date(2026, 1, 5),
                    summary="测试分录",
                    account_code=account_code,
                    account_name=account_name,
                    debit_amount=debit,
                    credit_amount=credit,
                    counterparty="A公司",
                    review_status=review_status,
                    post_status=post_status,
                )
            )
        db.commit()
        return job.id
    finally:
        db.close()


def test_post_job_marks_entries_posted(client):
    test_client, TestingSessionLocal = client
    job_id = _seed_job(TestingSessionLocal, review_status="verified")

    response = test_client.post(f"/api/import-jobs/{job_id}/post")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    assert data["posted"] == 2
    assert data["total"] == 2
    assert data["posted_at"]

    db = TestingSessionLocal()
    try:
        entries = db.query(AccountingEntry).filter(AccountingEntry.import_job_id == job_id).all()
        assert len(entries) == 2
        assert all(e.post_status == "posted" for e in entries)
        assert all(e.posted_at is not None for e in entries)
    finally:
        db.close()


def test_post_job_rejects_draft_entries(client):
    test_client, TestingSessionLocal = client
    job_id = _seed_job(TestingSessionLocal, review_status="draft")

    response = test_client.post(f"/api/import-jobs/{job_id}/post")
    assert response.status_code == 400
    assert "未复核通过" in response.json()["detail"]


def test_post_job_unknown_job_404(client):
    test_client, _ = client
    response = test_client.post("/api/import-jobs/9999/post")
    assert response.status_code == 404


def test_post_job_idempotent_for_already_posted(client):
    test_client, TestingSessionLocal = client
    job_id = _seed_job(TestingSessionLocal, review_status="ready", post_status="posted")

    response = test_client.post(f"/api/import-jobs/{job_id}/post")
    assert response.status_code == 200
    assert response.json()["posted"] == 0
    assert response.json()["total"] == 2


def test_export_only_includes_posted_entries(client):
    test_client, TestingSessionLocal = client
    job_id = _seed_job(TestingSessionLocal, review_status="ready", post_status="draft")

    unposted = test_client.get(f"/api/import-jobs/{job_id}/export", params={"format": "json"})
    assert unposted.status_code == 200
    assert unposted.json() == []

    test_client.post(f"/api/import-jobs/{job_id}/post")
    posted = test_client.get(f"/api/import-jobs/{job_id}/export", params={"format": "json"})
    assert posted.status_code == 200
    assert len(posted.json()) == 2
