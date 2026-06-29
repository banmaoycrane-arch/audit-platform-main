# -*- coding: utf-8 -*-
"""
模块功能：团队与账簿授权 API 测试
业务场景：验证团队创建、团队成员维护、账簿授权查询与撤销接口
政策依据：会计信息系统内部控制规范——团队隔离、账簿授权与权限撤销管理
输入数据：HTTP 请求（JSON、路径参数、Bearer Token）
输出结果：测试断言结果
创建日期：2026-06-18
更新记录：
    2026-06-18  初始创建团队与账簿授权 API 测试
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app


@pytest.fixture
def client():
    """
    功能描述：创建测试客户端，隔离团队与账簿授权 API 测试数据。
    业务逻辑：每个测试使用独立内存数据库，避免不同测试之间的用户、团队、账簿互相影响。
    会计口径：权限测试需要独立账簿环境，确保授权列表和撤销结果可准确核对。

    Returns:
        TestClient: 已覆盖数据库依赖的 FastAPI 测试客户端。

    注意事项：
        1. 测试结束后清理依赖覆盖和内存数据库表结构。
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
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _register_user(client: TestClient, username: str, phone: str | None = None) -> tuple[dict, int]:
    """
    功能描述：注册测试用户并返回认证头和用户 ID。
    业务逻辑：团队和账簿接口均要求登录用户，通过注册接口获得 Bearer Token。
    会计口径：每个权限动作都应明确操作人，测试中用用户 ID 验证授权归属。

    Args:
        client: FastAPI 测试客户端。
        username: 测试用户名。
        phone: 测试手机号，可为空。

    Returns:
        tuple[dict, int]: 认证请求头和注册用户 ID。

    注意事项：
        1. 用户名在单个测试数据库内保持唯一。
    """
    payload = {
        "username": username,
        "password": "testpass123",
        "agreed_terms": True,
        "agreed_privacy": True,
    }
    if phone:
        payload["phone"] = phone

    register_response = client.post("/api/auth/register", json=payload)
    assert register_response.status_code == 200

    token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me_response = client.get("/api/auth/me", headers=headers)
    assert me_response.status_code == 200
    return headers, me_response.json()["id"]


def test_team_create_list_members_and_add_member(client):
    """
    功能描述：验证团队创建、当前用户团队列表、成员列表、添加成员接口。
    业务逻辑：创建团队后创建者自动成为团队成员，再将第二个用户加入同一团队。
    会计口径：团队对应协作组织，成员列表应反映当前可参与同一账簿/项目工作的人员范围。
    """
    owner_headers, owner_id = _register_user(client, "team_owner", "13800138100")
    _, member_id = _register_user(client, "team_member", "13800138101")

    # 创建团队：创建者自动归属该团队。
    create_response = client.post(
        "/api/teams",
        json={"name": "审计一部团队", "type": "firm"},
        headers=owner_headers,
    )
    assert create_response.status_code == 200
    team_body = create_response.json()
    assert team_body["name"] == "审计一部团队"
    assert team_body["type"] == "firm"
    assert "id" in team_body
    team_id = team_body["id"]

    # 查询当前用户团队列表：应包含刚创建的团队。
    list_response = client.get("/api/teams", headers=owner_headers)
    assert list_response.status_code == 200
    teams = list_response.json()
    assert len(teams) == 1
    assert teams[0]["id"] == team_id
    assert teams[0]["name"] == "审计一部团队"

    # 查询成员：创建者已自动成为成员。
    members_response = client.get(f"/api/teams/{team_id}/members", headers=owner_headers)
    assert members_response.status_code == 200
    members = members_response.json()
    assert any(member["id"] == owner_id for member in members)

    # 添加第二个用户为团队成员。
    add_response = client.post(
        f"/api/teams/{team_id}/members",
        json={"user_id": member_id, "role": "member"},
        headers=owner_headers,
    )
    assert add_response.status_code == 200
    added_member = add_response.json()
    assert added_member["id"] == member_id
    assert added_member["username"] == "team_member"
    assert added_member["team_id"] == team_id

    # 再次查询成员：应同时包含创建者和新增成员。
    members_response = client.get(f"/api/teams/{team_id}/members", headers=owner_headers)
    assert members_response.status_code == 200
    member_ids = {member["id"] for member in members_response.json()}
    assert {owner_id, member_id} <= member_ids


def test_ledger_auths_list_and_revoke(client):
    """
    功能描述：验证账簿授权列表查询与授权撤销接口。
    业务逻辑：创建团队和账簿后，管理员给第二个用户授权，再查询和撤销该授权。
    会计口径：账簿授权列表对应权限分配表，撤销后该用户不应继续出现在授权清单中。
    """
    admin_headers, admin_id = _register_user(client, "ledger_admin", "13800138110")
    _, viewer_id = _register_user(client, "ledger_viewer", "13800138111")

    # 创建团队，确保账簿有明确的团队归属。
    team_response = client.post(
        "/api/teams",
        json={"name": "客户账簿管理团队", "type": "firm"},
        headers=admin_headers,
    )
    assert team_response.status_code == 200
    team_id = team_response.json()["id"]

    # 创建账簿：创建者自动获得 admin 授权。
    ledger_response = client.post(
        "/api/ledgers",
        json={"team_id": team_id, "name": "A客户2026年账簿"},
        headers=admin_headers,
    )
    assert ledger_response.status_code == 200
    ledger_id = ledger_response.json()["id"]

    # 给第二个用户授权 viewer 角色，用于后续撤销。
    auth_response = client.post(
        f"/api/ledgers/{ledger_id}/auth",
        json={"user_id": viewer_id, "role": "viewer"},
        headers=admin_headers,
    )
    assert auth_response.status_code == 200
    assert auth_response.json()["user_id"] == viewer_id
    assert auth_response.json()["role"] == "viewer"

    ledger_list_response = client.get("/api/ledgers", headers=admin_headers)
    assert ledger_list_response.status_code == 200
    ledger_list = ledger_list_response.json()
    assert any(ledger["id"] == ledger_id and ledger["role"] == "admin" for ledger in ledger_list)

    switch_response = client.post(f"/api/ledgers/{ledger_id}/switch", headers=admin_headers)
    assert switch_response.status_code == 200
    assert switch_response.json()["ledger_id"] == ledger_id

    # 查询授权列表：应包含 admin 和 viewer 两条授权记录。
    auths_response = client.get(f"/api/ledgers/{ledger_id}/auths", headers=admin_headers)
    assert auths_response.status_code == 200
    auths = auths_response.json()
    assert any(auth["user_id"] == admin_id and auth["role"] == "admin" for auth in auths)
    viewer_auth = next(auth for auth in auths if auth["user_id"] == viewer_id)
    assert viewer_auth["ledger_id"] == ledger_id
    assert viewer_auth["role"] == "viewer"

    # 撤销 viewer 授权。
    revoke_response = client.delete(
        f"/api/ledgers/{ledger_id}/auths/{viewer_auth['id']}",
        headers=admin_headers,
    )
    assert revoke_response.status_code == 200
    revoke_body = revoke_response.json()
    assert revoke_body["auth_id"] == viewer_auth["id"]
    assert revoke_body["user_id"] == viewer_id
    assert revoke_body["ledger_id"] == ledger_id

    # 再次查询授权列表：viewer 授权应已被移除，admin 授权仍保留。
    auths_after_revoke_response = client.get(
        f"/api/ledgers/{ledger_id}/auths",
        headers=admin_headers,
    )
    assert auths_after_revoke_response.status_code == 200
    auths_after_revoke = auths_after_revoke_response.json()
    assert any(auth["user_id"] == admin_id for auth in auths_after_revoke)
    assert all(auth["user_id"] != viewer_id for auth in auths_after_revoke)
