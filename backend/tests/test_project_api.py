# -*- coding: utf-8 -*-
"""
模块功能：项目管理 API 测试
业务场景：验证创建项目、关联账套、分配人员三个核心接口
政策依据：会计师事务所质量控制准则——项目立项与人员分派
输入数据：HTTP 请求（JSON 或路径参数）
输出结果：测试断言结果
创建日期：2026-06-18
更新记录：
    2026-06-18  初始创建项目 API 测试
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.models.team import Team
from app.models.ledger import Ledger
from app.models.user import User


@pytest.fixture
def client():
    """
    测试客户端 fixture。

    使用内存 SQLite 数据库，覆盖 get_db 依赖，确保测试隔离。
    """
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


def _get_auth_headers(client: TestClient) -> dict:
    """
    注册并登录，获取 Bearer Token 认证头。

    Args:
        client: FastAPI 测试客户端

    Returns:
        dict: 包含 Authorization 头的字典
    """
    resp = client.post(
        "/api/auth/register",
        json={
            "username": "project_test_user",
            "password": "testpass123",
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    assert resp.status_code == 200
    resp = client.post(
        "/api/auth/login/password",
        json={"username": "project_test_user", "password": "testpass123"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_team_and_ledger(client: TestClient):
    """
    在测试数据库中直接创建团队与账套记录。

    业务逻辑：项目 API 依赖 team 和 ledger 外键，
    但当前系统未提供独立的 team/ledger 创建 API，
    故通过 SQLAlchemy 直接插入基础数据。

    Args:
        client: FastAPI 测试客户端

    Returns:
        tuple: (team_id, ledger_id)
    """
    SessionLocal = client._SessionLocal  # type: ignore[attr-defined]
    db = SessionLocal()
    try:
        team = Team(name="测试事务所团队", type="firm")
        db.add(team)
        db.commit()
        db.refresh(team)

        ledger = Ledger(name="测试客户账套", team_id=team.id, status="active")
        db.add(ledger)
        db.commit()
        db.refresh(ledger)

        return team.id, ledger.id
    finally:
        db.close()


def _create_second_user(client: TestClient) -> int:
    """
    注册第二个用户，用于人员分配测试。

    Args:
        client: FastAPI 测试客户端

    Returns:
        int: 新用户 ID
    """
    resp = client.post(
        "/api/auth/register",
        json={
            "username": "second_user",
            "password": "testpass123",
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_create_project_success(client):
    """
    测试：成功创建项目。

    业务逻辑：创建项目后自动将当前用户加入为 manager，
    并通过 list_projects 可查询到该项目。
    """
    headers = _get_auth_headers(client)
    team_id, _ = _create_team_and_ledger(client)

    resp = client.post(
        "/api/projects",
        json={
            "team_id": team_id,
            "name": "2026年度年报审计项目",
            "project_type": "audit",
            "status": "active",
            "start_date": "2026-01-01",
            "end_date": "2026-04-30",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "2026年度年报审计项目"
    assert body["team_id"] == team_id
    assert body["type"] == "audit"
    assert body["status"] == "active"
    assert body["start_date"] == "2026-01-01"
    assert body["end_date"] == "2026-04-30"
    assert "id" in body

    # 验证：当前用户可在项目列表中查询到该项目
    list_resp = client.get("/api/projects", headers=headers)
    assert list_resp.status_code == 200
    projects = list_resp.json()
    assert any(p["id"] == body["id"] for p in projects)


def test_create_project_team_not_exist(client):
    """
    测试：创建项目时团队不存在，返回 400 错误。
    """
    headers = _get_auth_headers(client)

    resp = client.post(
        "/api/projects",
        json={
            "team_id": 9999,
            "name": "无效团队项目",
        },
        headers=headers,
    )
    assert resp.status_code == 400
    assert "团队不存在" in resp.json()["detail"]


def test_associate_ledger_to_project(client):
    """
    测试：关联账套到项目。

    业务逻辑：创建项目后，将账套关联到项目，
    验证关联接口返回正确的 project_id 和 ledger_id。
    """
    headers = _get_auth_headers(client)
    team_id, ledger_id = _create_team_and_ledger(client)

    # 先创建项目
    project_resp = client.post(
        "/api/projects",
        json={
            "team_id": team_id,
            "name": "关联账套测试项目",
        },
        headers=headers,
    )
    assert project_resp.status_code == 200
    project_id = project_resp.json()["id"]

    # 关联账套
    assoc_resp = client.post(
        f"/api/projects/{project_id}/ledgers",
        json={"ledger_id": ledger_id},
        headers=headers,
    )
    assert assoc_resp.status_code == 200
    body = assoc_resp.json()
    assert body["project_id"] == project_id
    assert body["ledger_id"] == ledger_id
    assert "id" in body


def test_associate_ledger_project_not_exist(client):
    """
    测试：关联账套时项目不存在，返回 404 错误。
    """
    headers = _get_auth_headers(client)
    _, ledger_id = _create_team_and_ledger(client)

    resp = client.post(
        "/api/projects/9999/ledgers",
        json={"ledger_id": ledger_id},
        headers=headers,
    )
    assert resp.status_code == 404
    assert "项目不存在" in resp.json()["detail"]


def test_associate_ledger_not_exist(client):
    """
    测试：关联账套时账套不存在，返回 400 错误。
    """
    headers = _get_auth_headers(client)
    team_id, _ = _create_team_and_ledger(client)

    project_resp = client.post(
        "/api/projects",
        json={"team_id": team_id, "name": "测试项目"},
        headers=headers,
    )
    project_id = project_resp.json()["id"]

    resp = client.post(
        f"/api/projects/{project_id}/ledgers",
        json={"ledger_id": 9999},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "账套不存在" in resp.json()["detail"]


def test_assign_member_to_project(client):
    """
    测试：分配人员到项目。

    业务逻辑：创建项目后，将另一名用户分配为 member，
    验证接口返回正确的 project_id、user_id 和 role。
    """
    headers = _get_auth_headers(client)
    team_id, _ = _create_team_and_ledger(client)

    # 先创建项目
    project_resp = client.post(
        "/api/projects",
        json={
            "team_id": team_id,
            "name": "人员分配测试项目",
        },
        headers=headers,
    )
    assert project_resp.status_code == 200
    project_id = project_resp.json()["id"]

    # 注册第二个用户并获取其 ID
    second_token = _create_second_user(client)
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {second_token}"})
    assert me_resp.status_code == 200
    second_user_id = me_resp.json()["id"]

    # 分配人员
    assign_resp = client.post(
        f"/api/projects/{project_id}/members",
        json={"user_id": second_user_id, "role": "member"},
        headers=headers,
    )
    assert assign_resp.status_code == 200
    body = assign_resp.json()
    assert body["project_id"] == project_id
    assert body["user_id"] == second_user_id
    assert body["role"] == "member"


def test_assign_member_project_not_exist(client):
    """
    测试：分配人员时项目不存在，返回 404 错误。
    """
    headers = _get_auth_headers(client)
    second_token = _create_second_user(client)
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {second_token}"})
    second_user_id = me_resp.json()["id"]

    resp = client.post(
        "/api/projects/9999/members",
        json={"user_id": second_user_id, "role": "member"},
        headers=headers,
    )
    assert resp.status_code == 404
    assert "项目不存在" in resp.json()["detail"]


def test_assign_member_user_not_exist(client):
    """
    测试：分配人员时用户不存在，返回 400 错误。
    """
    headers = _get_auth_headers(client)
    team_id, _ = _create_team_and_ledger(client)

    project_resp = client.post(
        "/api/projects",
        json={"team_id": team_id, "name": "测试项目"},
        headers=headers,
    )
    project_id = project_resp.json()["id"]

    resp = client.post(
        f"/api/projects/{project_id}/members",
        json={"user_id": 9999, "role": "member"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "用户不存在" in resp.json()["detail"]


def test_list_projects_by_user(client):
    """
    测试：查询当前用户参与的项目列表。

    业务逻辑：创建多个项目后，list_projects 应返回所有当前用户参与的项目。
    """
    headers = _get_auth_headers(client)
    team_id, _ = _create_team_and_ledger(client)

    for i in range(3):
        resp = client.post(
            "/api/projects",
            json={
                "team_id": team_id,
                "name": f"项目{i + 1}",
            },
            headers=headers,
        )
        assert resp.status_code == 200

    list_resp = client.get("/api/projects", headers=headers)
    assert list_resp.status_code == 200
    projects = list_resp.json()
    assert len(projects) >= 3
    names = {p["name"] for p in projects}
    assert {"项目1", "项目2", "项目3"} <= names
