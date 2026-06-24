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


def register_user(client: TestClient, username: str, phone: str) -> str:
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "phone": phone,
            "password": "password123",
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_binding_request_approval_writes_authorization_relationships(client: TestClient):
    admin_token = register_user(client, "binding_admin", "13900001001")
    visitor_token = register_user(client, "binding_visitor", "13900001002")

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    visitor_headers = {"Authorization": f"Bearer {visitor_token}"}

    team_response = client.post(
        "/api/teams",
        json={"name": "绑定审批测试团队", "type": "company"},
        headers=admin_headers,
    )
    assert team_response.status_code == 200
    team_id = team_response.json()["id"]

    ledger_response = client.post(
        "/api/ledgers",
        json={"team_id": team_id, "name": "绑定审批测试账套"},
        headers=admin_headers,
    )
    assert ledger_response.status_code == 200
    ledger_id = ledger_response.json()["id"]

    project_response = client.post(
        "/api/projects",
        json={"team_id": team_id, "name": "绑定审批测试项目", "project_type": "accounting"},
        headers=admin_headers,
    )
    assert project_response.status_code == 200
    project_id = project_response.json()["id"]

    request_response = client.post(
        "/api/binding-requests",
        json={
            "team_id": team_id,
            "ledger_id": ledger_id,
            "project_id": project_id,
            "requested_role": "accountant",
            "reason": "参与本项目记账，需要访问账套。",
        },
        headers=visitor_headers,
    )
    assert request_response.status_code == 200
    request_id = request_response.json()["id"]
    assert request_response.json()["status"] == "pending"

    reviewable_response = client.get(
        "/api/binding-requests?scope=reviewable",
        headers=admin_headers,
    )
    assert reviewable_response.status_code == 200
    assert any(item["id"] == request_id for item in reviewable_response.json())

    approve_response = client.post(
        f"/api/binding-requests/{request_id}/approve",
        json={"review_comment": "同意加入项目记账。"},
        headers=admin_headers,
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"

    visitor_context_response = client.get("/api/auth/context", headers=visitor_headers)
    assert visitor_context_response.status_code == 200
    visitor_context = visitor_context_response.json()
    assert visitor_context["teams"][0]["id"] == team_id
    assert visitor_context["ledgers"][0]["id"] == ledger_id
    assert visitor_context["projects"][0]["id"] == project_id
    assert visitor_context["current_ledger_id"] == ledger_id
    assert "accounting_entity" in visitor_context["missing_bindings"]


def test_binding_requests_router_is_mounted(client: TestClient):
    """Regression: binding-requests routes must be registered in main.py."""
    visitor_token = register_user(client, "binding_route_check", "13900001099")
    response = client.post(
        "/api/binding-requests",
        json={"team_id": 1, "requested_role": "viewer"},
        headers={"Authorization": f"Bearer {visitor_token}"},
    )
    # Unmounted router returns 404; mounted router reaches business validation (400).
    assert response.status_code == 400
    assert response.json()["detail"] == "申请团队不存在"
