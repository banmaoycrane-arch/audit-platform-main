import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _initialize_types(test_client):
    resp = test_client.post("/api/accounting-units/types/initialize")
    assert resp.status_code == 200


def _create_unit(test_client, unit_name="华东销售部", description="负责华东区域收入核算"):
    return test_client.post(
        "/api/accounting-units/",
        json={
            "unit_name": unit_name,
            "unit_type_code": "department",
            "description": description,
        },
    )


def test_initialize_types_and_list_returns_at_least_8(client):
    init_resp = client.post("/api/accounting-units/types/initialize")
    assert init_resp.status_code == 200
    assert init_resp.json()["count"] >= 8

    list_resp = client.get("/api/accounting-units/types")
    assert list_resp.status_code == 200
    types = list_resp.json()
    assert len(types) >= 8
    assert "department" in {item["type_code"] for item in types}


def test_create_accounting_unit(client):
    _initialize_types(client)

    resp = _create_unit(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["unit_name"] == "华东销售部"
    assert body["description"] == "负责华东区域收入核算"
    assert body["is_active"] is True


def test_keyword_search_returns_unit(client):
    _initialize_types(client)
    created = _create_unit(client, unit_name="渠道运营中心", description="重点平台渠道费用归集").json()

    resp = client.get("/api/accounting-units/", params={"keyword": "平台渠道"})
    assert resp.status_code == 200
    assert any(item["id"] == created["id"] for item in resp.json())


def test_merge_two_units_returns_combination_and_members(client):
    _initialize_types(client)
    unit_a = _create_unit(client, unit_name="门店A").json()
    unit_b = _create_unit(client, unit_name="门店B").json()

    resp = client.post(
        "/api/accounting-units/merge",
        json={
            "unit_ids": [unit_a["id"], unit_b["id"]],
            "combination_name": "门店合并核算组",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["combination_name"] == "门店合并核算组"
    assert body["combination_type"] == "merged"
    assert len(body["members"]) == 2
    assert {m["unit_id"] for m in body["members"]} == {unit_a["id"], unit_b["id"]}


def test_split_combination_returns_ok(client):
    _initialize_types(client)
    unit_a = _create_unit(client, unit_name="项目A").json()
    unit_b = _create_unit(client, unit_name="项目B").json()
    combination = client.post(
        "/api/accounting-units/merge",
        json={"unit_ids": [unit_a["id"], unit_b["id"]], "combination_name": "项目临时合并"},
    ).json()

    resp = client.post(f"/api/accounting-units/combinations/{combination['id']}/split")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert set(body["member_unit_ids"]) == {unit_a["id"], unit_b["id"]}


def test_create_and_query_version_history(client):
    _initialize_types(client)
    unit = _create_unit(client, unit_name="成本中心A").json()

    create_resp = client.post(
        f"/api/accounting-units/{unit['id']}/versions",
        json={
            "version_name": "启用版本",
            "effective_date": "2026-01-01",
            "changes": {"description": "新增成本中心"},
            "change_reason": "管理口径调整",
            "changed_by": "tester",
        },
    )
    assert create_resp.status_code == 200
    version = create_resp.json()
    assert version["version_number"] == 1
    assert version["effective_date"] == "2026-01-01"

    list_resp = client.get(f"/api/accounting-units/{unit['id']}/versions")
    assert list_resp.status_code == 200
    versions = list_resp.json()
    assert len(versions) == 1
    assert versions[0]["version_name"] == "启用版本"


def test_get_unknown_unit_returns_404(client):
    resp = client.get("/api/accounting-units/9999")
    assert resp.status_code == 404
