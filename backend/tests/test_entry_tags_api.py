from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import AccountingEntry, EntryTag, ImportJob, Organization
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
        org = Organization(name="标签测试", fiscal_year=2026)
        db.add(org)
        db.flush()
        job = ImportJob(organization_id=org.id, status="completed", source_type="voucher_import")
        db.add(job)
        db.flush()
        entry = AccountingEntry(
            organization_id=org.id,
            import_job_id=job.id,
            voucher_no="记-001",
            voucher_date=date(2026, 1, 1),
            summary="支付供应商货款",
            account_code="2202",
            account_name="应付账款",
            debit_amount=Decimal("1000"),
            credit_amount=Decimal("0"),
            counterparty="供应商A",
            normalized_text="记-001 支付供应商货款 应付账款 供应商A",
            entry_line_no=1,
        )
        other_entry = AccountingEntry(
            organization_id=org.id,
            import_job_id=job.id,
            voucher_no="记-002",
            voucher_date=date(2026, 1, 2),
            summary="采购材料",
            account_code="1403",
            account_name="原材料",
            debit_amount=Decimal("500"),
            credit_amount=Decimal("0"),
            normalized_text="记-002 采购材料 原材料",
            entry_line_no=1,
        )
        db.add(entry)
        db.add(other_entry)
        db.commit()
        return entry.id, other_entry.id
    finally:
        db.close()


def test_get_tags_empty_list(client):
    test_client, TestingSessionLocal = client
    entry_id, _ = _seed(TestingSessionLocal)

    resp = test_client.get(f"/api/entries/{entry_id}/tags")

    assert resp.status_code == 200
    assert resp.json() == []


def test_post_tag_returns_full_fields_and_vector_pending(client):
    test_client, TestingSessionLocal = client
    entry_id, _ = _seed(TestingSessionLocal)

    resp = test_client.post(
        f"/api/entries/{entry_id}/tags",
        json={"tag_type": "counterparty", "tag_value": "供应商A"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["entry_id"] == entry_id
    assert body["tag_name"] == "供应商A"
    assert body["tag_type"] == "counterparty"
    assert body["tag_value"] == "供应商A"
    assert body["tag_value_normalized"] == "供应商a"
    assert body["tag_source"] == "manual"
    assert body["confidence"] == 1.0
    assert body["reviewed_by_user"] is True
    assert body["vector_pending"] is True
    assert body["created_at"]


def test_get_tags_returns_created_tag(client):
    test_client, TestingSessionLocal = client
    entry_id, _ = _seed(TestingSessionLocal)
    created = test_client.post(
        f"/api/entries/{entry_id}/tags",
        json={"tag_name": "项目一期", "tag_type": "project", "tag_value": "项目一期"},
    ).json()

    resp = test_client.get(f"/api/entries/{entry_id}/tags")

    assert resp.status_code == 200
    tags = resp.json()
    assert len(tags) == 1
    assert tags[0]["id"] == created["id"]
    assert tags[0]["tag_type"] == "project"


def test_delete_tag_success(client):
    test_client, TestingSessionLocal = client
    entry_id, _ = _seed(TestingSessionLocal)
    tag_id = test_client.post(
        f"/api/entries/{entry_id}/tags",
        json={"tag_type": "department", "tag_value": "财务部"},
    ).json()["id"]

    resp = test_client.delete(f"/api/entries/{entry_id}/tags/{tag_id}")

    assert resp.status_code == 200
    assert resp.json() == {"deleted": 1}
    assert test_client.get(f"/api/entries/{entry_id}/tags").json() == []


def test_delete_tag_not_belonging_to_entry_returns_404(client):
    test_client, TestingSessionLocal = client
    entry_id, other_entry_id = _seed(TestingSessionLocal)
    tag_id = test_client.post(
        f"/api/entries/{other_entry_id}/tags",
        json={"tag_type": "project", "tag_value": "其他项目"},
    ).json()["id"]

    resp = test_client.delete(f"/api/entries/{entry_id}/tags/{tag_id}")

    assert resp.status_code == 404


def test_patch_tags_legacy_api_sets_vector_pending(client):
    test_client, TestingSessionLocal = client
    entry_id, _ = _seed(TestingSessionLocal)

    resp = test_client.patch(f"/api/entries/{entry_id}/tags", json={"tags": ["供应商A", "项目一期"]})

    assert resp.status_code == 200
    assert resp.json() == {"entry_id": entry_id, "tags": ["供应商A", "项目一期"]}
    db = TestingSessionLocal()
    try:
        tags = db.query(EntryTag).filter(EntryTag.entry_id == entry_id).all()
        assert len(tags) == 2
        assert all(tag.vector_pending for tag in tags)
        assert {tag.tag_type for tag in tags} == {"manual"}
        assert {tag.tag_source for tag in tags} == {"manual"}
        assert all(tag.reviewed_by_user for tag in tags)
    finally:
        db.close()


def test_sync_vector_unavailable_returns_200_and_keeps_pending(client, monkeypatch):
    test_client, TestingSessionLocal = client
    entry_id, _ = _seed(TestingSessionLocal)
    tag_id = test_client.post(
        f"/api/entries/{entry_id}/tags",
        json={"tag_type": "counterparty", "tag_value": "供应商A"},
    ).json()["id"]
    monkeypatch.setattr("app.services.accounting.entry_tag_vector_service.safe_vector_store", lambda: None)

    resp = test_client.post("/api/entry-tags/sync-vector", params={"limit": 100})

    assert resp.status_code == 200
    body = resp.json()
    assert body["vector_available"] is False
    assert body["synced_count"] == 0
    assert body["pending_count"] == 1
    db = TestingSessionLocal()
    try:
        tag = db.get(EntryTag, tag_id)
        assert tag.vector_pending is True
    finally:
        db.close()


def test_unknown_entry_get_and_post_tags_return_404(client):
    test_client, TestingSessionLocal = client
    _seed(TestingSessionLocal)

    get_resp = test_client.get("/api/entries/9999/tags")
    post_resp = test_client.post("/api/entries/9999/tags", json={"tag_value": "不存在"})

    assert get_resp.status_code == 404
    assert post_resp.status_code == 404
