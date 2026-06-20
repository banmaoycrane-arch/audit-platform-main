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


def test_initialize_industries_and_list(client):
    resp = client.post("/api/materials/industries/initialize")
    assert resp.status_code == 200
    assert len(resp.json()) >= 3

    list_resp = client.get("/api/materials/industries")
    assert list_resp.status_code == 200
    industries = list_resp.json()
    assert len(industries) >= 3
    assert any(item["industry_name"] == "制造业" for item in industries)


def test_recommend_manufacturing_granularity(client):
    client.post("/api/materials/industries/initialize")

    resp = client.get(
        "/api/materials/industries/recommend-granularity",
        params={"industry": "制造业"},
    )
    assert resp.status_code == 200
    body = resp.json()
    granularities = body["granularities"]
    assert "material" in granularities or "product" in granularities


def test_create_material_and_get_detail(client):
    resp = client.post(
        "/api/materials/",
        json={
            "material_code": "M-001",
            "material_name": "测试原材料",
            "material_type": "raw_material",
            "unit": "千克",
        },
    )
    assert resp.status_code == 200
    material = resp.json()
    assert material["material_code"] == "M-001"
    assert material["material_name"] == "测试原材料"

    detail = client.get(f"/api/materials/{material['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == material["id"]


def test_create_parent_child_materials_and_bom(client):
    parent = client.post(
        "/api/materials/",
        json={
            "material_code": "FG-001",
            "material_name": "测试成品",
            "material_type": "finished",
            "unit": "件",
        },
    ).json()
    child = client.post(
        "/api/materials/",
        json={
            "material_code": "RM-001",
            "material_name": "测试子件",
            "material_type": "raw_material",
            "unit": "千克",
        },
    ).json()

    resp = client.post(
        "/api/materials/bom",
        json={
            "parent_material_id": parent["id"],
            "child_material_id": child["id"],
            "quantity": 2.5,
            "loss_rate": 0.03,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["child_material_id"] == child["id"]

    bom_resp = client.get(f"/api/materials/{parent['id']}/bom")
    assert bom_resp.status_code == 200
    bom = bom_resp.json()
    assert bom["material_id"] == parent["id"]
    assert len(bom["children"]) == 1
    assert bom["children"][0]["material_id"] == child["id"]
    assert bom["children"][0]["material_name"] == "测试子件"


def test_unknown_material_returns_404(client):
    resp = client.get("/api/materials/9999")
    assert resp.status_code == 404

    bom_resp = client.get("/api/materials/9999/bom")
    assert bom_resp.status_code == 404
