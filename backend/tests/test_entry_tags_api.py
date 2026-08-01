from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import AccountingEntry, EntryTag, ImportJob, Organization, TagCategory
from app.models.ledger import Ledger
from app.models.team import Team
from app.db.session import Base, get_db
from app.main import app

from tests.conftest import register_auth_headers


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
            test_client._auth_headers = register_auth_headers(test_client)

            original_request = test_client.request

            def _request_with_auth(method, url, **kwargs):
                headers = kwargs.pop("headers", {}) or {}
                headers.update(test_client._auth_headers)
                return original_request(method, url, headers=headers, **kwargs)

            test_client.request = _request_with_auth
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


def test_get_entries_tags_redirects_to_entry_tags(client):
    """GET /api/entries/{id}/tags 废弃后 307 重定向到 /api/entry-tags（api-boundary-governance-plan Phase 4）。"""
    test_client, _ = client
    resp = test_client.get("/api/entries/123/tags", follow_redirects=False)
    assert resp.status_code == 307
    location = resp.headers["location"]
    assert "/api/entry-tags/tags" in location
    assert "entry_id=123" in location


def test_post_entries_tags_redirects_to_entry_tags(client):
    """POST /api/entries/{id}/tags 废弃后 307 重定向（body 结构不同，调用方应迁移至 /api/entry-tags）。"""
    test_client, _ = client
    resp = test_client.post(
        "/api/entries/123/tags",
        json={"tag_value": "x"},
        follow_redirects=False,
    )
    assert resp.status_code == 307
    assert "/api/entry-tags/tags" in resp.headers["location"]


def test_delete_entries_tags_redirects_to_entry_tags(client):
    """DELETE /api/entries/{id}/tags/{tag_id} 废弃后 307 重定向。"""
    test_client, _ = client
    resp = test_client.delete("/api/entries/123/tags/5", follow_redirects=False)
    assert resp.status_code == 307
    assert "/api/entry-tags/tags/5" in resp.headers["location"]


def test_entries_tags_redirect_preserves_query(client):
    """旧路径 307 重定向保留 query 参数。"""
    test_client, _ = client
    resp = test_client.get(
        "/api/entries/123/tags?category_code=project",
        follow_redirects=False,
    )
    assert resp.status_code == 307
    location = resp.headers["location"]
    assert "entry_id=123" in location
    assert "category_code=project" in location


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
    # 直接 DB 写入 EntryTag（vector_pending=True），不再走已废弃的旧 POST 端点
    db = TestingSessionLocal()
    try:
        tag = EntryTag(
            entry_id=entry_id,
            tag_name="counterparty:供应商A",
            tag_type="counterparty",
            tag_value="供应商A",
            tag_value_normalized="供应商a",
            tag_source="manual",
            confidence=1.0,
            reviewed_by_user=True,
            vector_pending=True,
        )
        db.add(tag)
        db.commit()
        db.refresh(tag)
        tag_id = tag.id
    finally:
        db.close()
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


def test_openapi_marks_entries_tags_deprecated(client):
    """OpenAPI schema 标记 /api/entries/{id}/tags 端点为 deprecated。"""
    test_client, _ = client
    resp = test_client.get("/openapi.json")
    schema = resp.json()
    found_deprecated = False
    for path, methods in schema["paths"].items():
        if path.startswith("/api/entries/{entry_id}/tags"):
            for op in methods.values():
                if isinstance(op, dict) and op.get("deprecated"):
                    found_deprecated = True
    assert found_deprecated, "entries 内嵌 tags 端点应标记 deprecated"


def _seed_ledger(TestingSessionLocal) -> int:
    db = TestingSessionLocal()
    try:
        team = Team(name="分类测试团队", type="virtual")
        db.add(team)
        db.flush()
        ledger = Ledger(name="分类测试账簿", team_id=team.id)
        db.add(ledger)
        db.commit()
        return ledger.id
    finally:
        db.close()


def test_create_tag_category_persists_and_lists(client):
    test_client, TestingSessionLocal = client
    ledger_id = _seed_ledger(TestingSessionLocal)

    create_resp = test_client.post(
        f"/api/entry-tags/categories?ledger_id={ledger_id}",
        json={"code": "product_line", "name": "产品线"},
    )
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["code"] == "product_line"
    assert created["name"] == "产品线"

    list_resp = test_client.get(f"/api/entry-tags/categories?ledger_id={ledger_id}&status=all")
    assert list_resp.status_code == 200
    codes = [node["code"] for node in list_resp.json()]
    assert "product_line" in codes

    db = TestingSessionLocal()
    try:
        row = db.query(TagCategory).filter(TagCategory.code == "product_line").one()
        assert row.ledger_id == ledger_id
        assert row.name == "产品线"
    finally:
        db.close()


def test_batch_get_entry_tags_returns_category_fields(client):
    test_client, TestingSessionLocal = client
    ledger_id = _seed_ledger(TestingSessionLocal)
    db = TestingSessionLocal()
    try:
        org = Organization(name="批量标签", fiscal_year=2026)
        db.add(org)
        db.flush()
        job = ImportJob(organization_id=org.id, status="completed", source_type="voucher_import")
        db.add(job)
        db.flush()
        category = TagCategory(ledger_id=ledger_id, code="dept", name="部门")
        db.add(category)
        db.flush()
        entry = AccountingEntry(
            organization_id=org.id,
            import_job_id=job.id,
            ledger_id=ledger_id,
            voucher_no="记-010",
            voucher_date=date(2026, 1, 10),
            summary="测试",
            account_code="1002",
            account_name="银行存款",
            debit_amount=Decimal("100"),
            credit_amount=Decimal("0"),
            normalized_text="记-010",
            entry_line_no=1,
        )
        db.add(entry)
        db.flush()
        db.add(
            EntryTag(
                entry_id=entry.id,
                ledger_id=ledger_id,
                category_id=category.id,
                tag_name="dept",
                tag_value="财务部",
                display_name="财务部",
            )
        )
        db.commit()
        entry_id = entry.id
    finally:
        db.close()

    resp = test_client.post(
        "/api/entry-tags/tags/batch",
        json={"entry_ids": [entry_id], "ledger_id": ledger_id},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["category_code"] == "dept"
    assert body[0]["category_name"] == "部门"
    assert body[0]["tag_value"] == "财务部"
