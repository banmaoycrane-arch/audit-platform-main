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


def _create_entity(test_client, **overrides):
    payload = {
        "entity_name": "母公司本部",
        "entity_type": "company",
        "entity_category": "parent",
        "is_accounting_entity": True,
        "is_legal_entity": True,
        "tags": [{"tag": "集团本部", "tag_type": "alias"}],
    }
    payload.update(overrides)
    return test_client.post("/api/entities", json=payload)


def test_create_entity_with_tags_and_search(client):
    response = _create_entity(client)
    assert response.status_code == 200
    body = response.json()
    assert body["entity_name"] == "母公司本部"
    assert body["is_accounting_entity"] is True

    # 通过别名标签语义搜索
    search_response = client.get("/api/entities/search", params={"name": "集团本部"})
    assert search_response.status_code == 200
    assert any(item["id"] == body["id"] for item in search_response.json())


def test_list_entities_filter(client):
    _create_entity(client, entity_name="A", is_accounting_entity=True)
    _create_entity(client, entity_name="B", is_accounting_entity=False)

    response = client.get("/api/entities", params={"accounting_entity": True})
    assert response.status_code == 200
    names = [item["entity_name"] for item in response.json()]
    assert "A" in names
    assert "B" not in names


def test_create_entity_keeps_ledger_binding(client):
    response = _create_entity(client, entity_name="账套会计主体", ledger_id=99)
    assert response.status_code == 200
    body = response.json()
    assert body["ledger_id"] == 99
    assert body["is_accounting_entity"] is True


def test_virtual_set_flow(client):
    a = _create_entity(client, entity_name="子公司A").json()
    b = _create_entity(client, entity_name="子公司B").json()

    vs = client.post(
        "/api/entities/virtual-sets",
        json={"set_name": "XX集团", "set_type": "group"},
    ).json()

    for entity in (a, b):
        resp = client.post(
            f"/api/entities/virtual-sets/{vs['id']}/members/{entity['id']}"
        )
        assert resp.status_code == 200

    members = client.get(f"/api/entities/virtual-sets/{vs['id']}/members").json()
    member_names = {m["entity_name"] for m in members}
    assert {"子公司A", "子公司B"} <= member_names


def test_scope_flow(client):
    a = _create_entity(client, entity_name="范围内主体").json()
    scope = client.post(
        "/api/entities/scopes",
        json={
            "scope_name": "2026年合并范围",
            "period_start": "2026-01-01",
            "period_end": "2026-12-31",
            "scope_type": "consolidation",
        },
    ).json()
    assert scope["scope_type"] == "consolidation"

    add_resp = client.post(
        f"/api/entities/scopes/{scope['id']}/members",
        json={"entity_id": a["id"], "member_type": "full"},
    )
    assert add_resp.status_code == 200

    members = client.get(f"/api/entities/scopes/{scope['id']}/members").json()
    assert any(m["id"] == a["id"] for m in members)


def test_detect_entity_confusion_no_data(client):
    response = client.post(
        "/api/entities/detect-confusion",
        json={
            "contract_entity_name": "未知合同主体",
            "invoice_entity_name": "未知发票主体",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] == "high"


def test_add_tag_for_unknown_entity_returns_404(client):
    response = client.post(
        "/api/entities/9999/tags",
        json={"tag": "test"},
    )
    assert response.status_code == 404


def test_get_hierarchy_unknown_entity_returns_404(client):
    response = client.get("/api/entities/9999/hierarchy")
    assert response.status_code == 404
