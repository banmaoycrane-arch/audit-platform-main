from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def register_user(username: str, phone: str) -> str:
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


def test_binding_request_approval_writes_authorization_relationships():
    admin_token = register_user("binding_admin", "13900001001")
    visitor_token = register_user("binding_visitor", "13900001002")

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
