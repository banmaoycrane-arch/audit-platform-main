# -*- coding: utf-8 -*-
"""
模块功能：生命周期状态转换 API 测试
业务场景：验证 Ledger 和 Project 的生命周期操作接口
政策依据：会计信息系统内部控制规范——关键状态变更必须留痕且可测试
输入数据：HTTP 请求（JSON 或路径参数）
输出结果：测试断言结果
创建日期：2026-06-18
更新记录：
    2026-06-18  初始创建生命周期转换测试
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
from app.models.project import Project
from app.models.project_member import ProjectMember


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
            "username": "lifecycle_test_user",
            "password": "testpass123",
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    assert resp.status_code == 200
    resp = client.post(
        "/api/auth/login/password",
        json={"username": "lifecycle_test_user", "password": "testpass123"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_team_and_ledger(client: TestClient, status: str = "active"):
    """
    在测试数据库中直接创建团队与账套记录。

    Args:
        client: FastAPI 测试客户端
        status: 账套初始状态

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

        ledger = Ledger(name="测试客户账套", team_id=team.id, status=status)
        db.add(ledger)
        db.flush()

        user = db.query(User).filter(User.username == "lifecycle_test_user").first()
        if user:
            db.add(UserLedgerAuth(user_id=user.id, ledger_id=ledger.id, role="admin"))

        db.commit()
        db.refresh(ledger)

        return team.id, ledger.id
    finally:
        db.close()


def _create_project(client: TestClient, status: str = "active") -> int:
    """
    在测试数据库中直接创建项目记录。

    Args:
        client: FastAPI 测试客户端
        status: 项目初始状态

    Returns:
        int: 项目 ID
    """
    SessionLocal = client._SessionLocal  # type: ignore[attr-defined]
    db = SessionLocal()
    try:
        team = Team(name="测试项目团队", type="firm")
        db.add(team)
        db.commit()
        db.refresh(team)

        project = Project(name="测试审计项目", team_id=team.id, status=status)
        db.add(project)
        db.commit()
        db.refresh(project)

        # 将当前测试用户加入项目成员
        user = db.query(User).filter(User.username == "lifecycle_test_user").first()
        if user:
            member = ProjectMember(project_id=project.id, user_id=user.id, role="manager")
            db.add(member)
            db.commit()

        return project.id
    finally:
        db.close()


# ── Ledger 生命周期测试 ──


def test_ledger_activate(client):
    """
    测试：激活账套。
    """
    headers = _get_auth_headers(client)
    _, ledger_id = _create_team_and_ledger(client, status="draft")

    resp = client.post(
        f"/api/ledgers/{ledger_id}/activate",
        json={"reason": "开始记账"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "active"


def test_ledger_suspend(client):
    """
    测试：暂停账套。
    """
    headers = _get_auth_headers(client)
    _, ledger_id = _create_team_and_ledger(client, status="active")

    resp = client.post(
        f"/api/ledgers/{ledger_id}/suspend",
        json={"reason": "客户要求暂停"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "suspended"


def test_ledger_archive(client):
    """
    测试：归档账套。
    """
    headers = _get_auth_headers(client)
    _, ledger_id = _create_team_and_ledger(client, status="active")

    resp = client.post(
        f"/api/ledgers/{ledger_id}/archive",
        json={"reason": "年度审计结束"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "archived"


def test_ledger_restore_from_suspended(client):
    """
    测试：从暂停状态恢复账套。
    """
    headers = _get_auth_headers(client)
    _, ledger_id = _create_team_and_ledger(client, status="suspended")

    resp = client.post(
        f"/api/ledgers/{ledger_id}/restore",
        json={"reason": "恢复记账"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "active"


def test_ledger_restore_from_archived(client):
    """
    测试：从归档状态恢复账套。
    """
    headers = _get_auth_headers(client)
    _, ledger_id = _create_team_and_ledger(client, status="archived")

    resp = client.post(
        f"/api/ledgers/{ledger_id}/restore",
        json={"reason": "需要查阅历史数据"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "active"


# ── Project 生命周期测试 ──


def test_project_start(client):
    """
    测试：启动项目。
    """
    headers = _get_auth_headers(client)
    project_id = _create_project(client, status="draft")

    resp = client.post(
        f"/api/projects/{project_id}/start",
        json={"reason": "项目立项通过"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "active"


def test_project_pause(client):
    """
    测试：暂停项目。
    """
    headers = _get_auth_headers(client)
    project_id = _create_project(client, status="active")

    resp = client.post(
        f"/api/projects/{project_id}/pause",
        json={"reason": "客户资料未齐全"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "paused"


def test_project_complete(client):
    """
    测试：完成项目。
    """
    headers = _get_auth_headers(client)
    project_id = _create_project(client, status="active")

    resp = client.post(
        f"/api/projects/{project_id}/complete",
        json={"reason": "审计报告已出具"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["completed_at"] is not None


def test_project_reopen_from_completed(client):
    """
    测试：从完成状态重新打开项目。
    """
    headers = _get_auth_headers(client)
    project_id = _create_project(client, status="completed")

    resp = client.post(
        f"/api/projects/{project_id}/reopen",
        json={"reason": "客户要求补充审计"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "active"


def test_project_reopen_from_paused(client):
    """
    测试：从暂停状态重新打开项目。
    """
    headers = _get_auth_headers(client)
    project_id = _create_project(client, status="paused")

    resp = client.post(
        f"/api/projects/{project_id}/reopen",
        json={"reason": "资料已补齐"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "active"


def test_project_cancel(client):
    """
    测试：取消项目。
    """
    headers = _get_auth_headers(client)
    project_id = _create_project(client, status="active")

    resp = client.post(
        f"/api/projects/{project_id}/cancel",
        json={"reason": "客户终止合同"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["cancelled_at"] is not None


def test_project_cancel_then_reopen(client):
    """
    测试：取消项目后重新打开。
    """
    headers = _get_auth_headers(client)
    project_id = _create_project(client, status="cancelled")

    resp = client.post(
        f"/api/projects/{project_id}/reopen",
        json={"reason": "客户恢复合作"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "active"


# ── 权限与边界测试 ──


def test_ledger_lifecycle_not_found(client):
    """
    测试：对不存在的账套执行生命周期操作，返回 404。
    """
    headers = _get_auth_headers(client)

    resp = client.post(
        "/api/ledgers/9999/activate",
        json={"reason": "测试"},
        headers=headers,
    )
    assert resp.status_code == 404
    assert "账套不存在" in resp.json()["detail"]


def test_project_lifecycle_not_found(client):
    """
    测试：对不存在的项目执行生命周期操作，返回 404。
    """
    headers = _get_auth_headers(client)

    resp = client.post(
        "/api/projects/9999/start",
        json={"reason": "测试"},
        headers=headers,
    )
    assert resp.status_code == 404
    assert "项目不存在" in resp.json()["detail"]
