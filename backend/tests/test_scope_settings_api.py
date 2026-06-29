"""账簿 / 团队 / 项目 / 主体 管理配置 API 测试。"""
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


def _register_user(client: TestClient, username: str, phone: str) -> tuple[dict, int]:
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "testpass123",
            "phone": phone,
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    return headers, me.json()["id"]


def _bootstrap_scope(client: TestClient, headers: dict) -> dict:
    team = client.post(
        "/api/teams",
        json={"name": "配置测试团队", "type": "firm"},
        headers=headers,
    ).json()
    ledger = client.post(
        "/api/ledgers",
        json={"team_id": team["id"], "name": "配置测试账簿"},
        headers=headers,
    ).json()
    project = client.post(
        "/api/projects",
        json={"team_id": team["id"], "name": "配置测试项目", "project_type": "audit"},
        headers=headers,
    ).json()
    return {"team_id": team["id"], "ledger_id": ledger["id"], "project_id": project["id"]}


def test_settings_catalog_returns_field_metadata(client: TestClient):
    response = client.get("/api/scope-settings/catalog")
    assert response.status_code == 200
    catalog = response.json()
    assert "ledger" in catalog
    assert catalog["ledger"]["fields"]["currency_mode"]["options"]
    assert catalog["team"]["fields"]["allow_multi_team_membership"]["type"] == "boolean"
    assert catalog["project"]["fields"]["allow_virtual_project"]["type"] == "boolean"


def test_ledger_settings_defaults_and_update(client: TestClient):
    headers, _ = _register_user(client, "ledger_cfg", "13800139001")
    scope = _bootstrap_scope(client, headers)

    get_resp = client.get(
        f"/api/scope-settings/ledger/{scope['ledger_id']}",
        headers=headers,
    )
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["settings"]["currency_mode"] == "single"
    assert body["settings"]["account_code_pattern"] == "4-2-2-2"
    assert body["settings"]["balance_direction_rule"] == "strict"

    put_resp = client.put(
        f"/api/scope-settings/ledger/{scope['ledger_id']}",
        headers=headers,
        json={
            "currency_mode": "multi",
            "base_currency": "USD",
            "account_code_pattern": "3-3-2-2",
            "balance_direction_rule": "natural",
        },
    )
    assert put_resp.status_code == 200
    updated = put_resp.json()["settings"]
    assert updated["currency_mode"] == "multi"
    assert updated["base_currency"] == "USD"
    assert updated["account_code_pattern"] == "3-3-2-2"
    assert updated["balance_direction_rule"] == "natural"


def test_team_and_project_settings_update(client: TestClient):
    headers, _ = _register_user(client, "team_proj_cfg", "13800139002")
    scope = _bootstrap_scope(client, headers)

    team_put = client.put(
        f"/api/scope-settings/team/{scope['team_id']}",
        headers=headers,
        json={
            "allow_multi_team_membership": True,
            "ledger_grant_policy": "manager_can_grant",
        },
    )
    assert team_put.status_code == 200
    team_settings = team_put.json()["settings"]
    assert team_settings["allow_multi_team_membership"] is True
    assert team_settings["ledger_grant_policy"] == "manager_can_grant"

    project_put = client.put(
        f"/api/scope-settings/project/{scope['project_id']}",
        headers=headers,
        json={
            "allow_merge": True,
            "allow_virtual_project": True,
            "virtual_project_label": "合并虚拟项目",
        },
    )
    assert project_put.status_code == 200
    project_settings = project_put.json()["settings"]
    assert project_settings["allow_merge"] is True
    assert project_settings["virtual_project_label"] == "合并虚拟项目"


def test_entity_scope_settings_on_ledger(client: TestClient):
    headers, _ = _register_user(client, "entity_cfg", "13800139003")
    scope = _bootstrap_scope(client, headers)

    put_resp = client.put(
        f"/api/scope-settings/entity/{scope['ledger_id']}",
        headers=headers,
        json={
            "allow_virtual_entity": False,
            "require_tax_registration": True,
            "default_entity_category": "holding",
        },
    )
    assert put_resp.status_code == 200
    settings = put_resp.json()["settings"]
    assert settings["allow_virtual_entity"] is False
    assert settings["require_tax_registration"] is True
    assert settings["default_entity_category"] == "holding"


def test_ledger_settings_update_requires_admin(client: TestClient):
    admin_headers, _ = _register_user(client, "ledger_admin", "13800139004")
    scope = _bootstrap_scope(client, admin_headers)
    viewer_headers, viewer_id = _register_user(client, "ledger_viewer", "13800139005")

    auth_resp = client.post(
        f"/api/ledgers/{scope['ledger_id']}/auth",
        headers=admin_headers,
        json={"user_id": viewer_id, "role": "viewer"},
    )
    assert auth_resp.status_code == 200

    forbidden = client.put(
        f"/api/scope-settings/ledger/{scope['ledger_id']}",
        headers=viewer_headers,
        json={"currency_mode": "multi"},
    )
    assert forbidden.status_code == 403


def test_project_settings_update_requires_manager(client: TestClient):
    owner_headers, owner_id = _register_user(client, "project_owner", "13800139006")
    scope = _bootstrap_scope(client, owner_headers)
    member_headers, member_id = _register_user(client, "project_member", "13800139007")

    team_join = client.post(
        f"/api/teams/{scope['team_id']}/members",
        headers=owner_headers,
        json={"user_id": member_id, "role": "member"},
    )
    assert team_join.status_code == 200

    member_join = client.post(
        f"/api/projects/{scope['project_id']}/members",
        headers=owner_headers,
        json={"user_id": member_id, "role": "member"},
    )
    assert member_join.status_code == 200

    forbidden = client.put(
        f"/api/scope-settings/project/{scope['project_id']}",
        headers=member_headers,
        json={"allow_merge": True},
    )
    assert forbidden.status_code == 403

    allowed = client.put(
        f"/api/scope-settings/project/{scope['project_id']}",
        headers=owner_headers,
        json={"allow_merge": True},
    )
    assert allowed.status_code == 200
    assert allowed.json()["settings"]["allow_merge"] is True
