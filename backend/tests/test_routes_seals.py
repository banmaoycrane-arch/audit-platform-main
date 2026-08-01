# -*- coding: utf-8 -*-
"""
模块功能：印章识别 API 集成测试。
业务场景：验证印章提取、列表、详情接口的权限校验与数据持久化。
政策依据：无。
输入数据：HTTP 请求与合成印章图片。
输出结果：测试通过/失败状态。
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建印章 API 集成测试
    2026-08-01  API 边界治理 Phase 5：主路径迁移至 /api/seals/...；
                新增旧路径 /api/v1/... 的 307 重定向兼容测试。
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from tests.conftest import register_auth_headers
from tests.fixtures.seals import ensure_default_fixtures


@pytest.fixture
def client():
    """创建使用内存数据库的测试客户端。"""
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
            test_client._SessionLocal = TestingSessionLocal
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _create_organization(db, user):
    """为测试创建组织并返回对象。"""
    from app.db.models import Organization
    org = Organization(name="印章测试企业")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _create_contract_with_source_file(client, headers, org, fixture_path, user_id):
    """创建合同、源文件、账簿与授权记录，返回合同 ID 与源文件 ID。"""
    db = client._SessionLocal()
    try:
        from app.db.models import Contract, SourceFile
        from app.models.team import Team
        from app.models.ledger import Ledger
        from app.models.user_ledger_auth import UserLedgerAuth

        team = Team(name="印章测试团队", type="firm")
        db.add(team)
        db.commit()
        db.refresh(team)

        ledger = Ledger(team_id=team.id, name="印章测试账簿")
        db.add(ledger)
        db.commit()
        db.refresh(ledger)

        auth = UserLedgerAuth(user_id=user_id, ledger_id=ledger.id, role="viewer")
        db.add(auth)
        db.commit()

        contract = Contract(
            organization_id=org.id,
            contract_type="sales",
            ledger_id=ledger.id,
        )
        db.add(contract)
        db.commit()
        db.refresh(contract)

        source_file = SourceFile(
            organization_id=org.id,
            import_job_id=0,
            ledger_id=ledger.id,
            filename="seal_test.png",
            file_type="png",
            storage_path=str(fixture_path),
        )
        db.add(source_file)
        db.commit()
        db.refresh(source_file)

        contract.source_file_id = source_file.id
        db.commit()
        return contract.id, source_file.id
    finally:
        db.close()


def test_extract_seals_requires_auth(client):
    """未登录用户应收到 401。"""
    response = client.post("/api/seals/contracts/1/extract")
    assert response.status_code == 401


def _current_user_id(client, headers):
    """通过 /api/auth/me 获取当前登录用户 ID。"""
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    return response.json()["id"]


def test_extract_seals_for_nonexistent_contract(client):
    """合同不存在应返回 404。"""
    headers = register_auth_headers(client, username="seal_extract_user_1", phone="13800138100")
    response = client.post("/api/seals/contracts/99999/extract", headers=headers)
    assert response.status_code == 404


def test_extract_seals_success(client, tmp_path):
    """正常流程应检测到印章并持久化记录。"""
    headers = register_auth_headers(client, username="seal_extract_user_2", phone="13800138101")
    user_id = _current_user_id(client, headers)
    fixture_paths = ensure_default_fixtures()

    db = client._SessionLocal()
    try:
        from app.db.models import Organization
        org = Organization(name="印章测试企业")
        db.add(org)
        db.commit()
        db.refresh(org)
    finally:
        db.close()

    contract_id, _ = _create_contract_with_source_file(
        client, headers, org, fixture_paths[0], user_id
    )

    response = client.post(
        f"/api/seals/contracts/{contract_id}/extract",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["contract_id"] == contract_id
    assert data["extracted_count"] >= 1
    assert len(data["seals"]) == data["extracted_count"]

    # 列表接口校验
    list_response = client.get(
        f"/api/seals/contracts/{contract_id}?page=1&size=10",
        headers=headers,
    )
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert list_data["total"] >= 1
    assert list_data["page"] == 1
    assert list_data["size"] == 10
    assert len(list_data["items"]) >= 1

    # 详情接口校验
    seal_id = list_data["items"][0]["id"]
    detail_response = client.get(f"/api/seals/{seal_id}", headers=headers)
    assert detail_response.status_code == 200
    detail_data = detail_response.json()
    assert detail_data["id"] == seal_id
    assert detail_data["contract_id"] == contract_id
    assert "bbox" in detail_data
    assert "seal_image_path" in detail_data


def test_list_seals_pagination(client, tmp_path):
    """分页参数应被正确应用。"""
    headers = register_auth_headers(client, username="seal_list_user", phone="13800138102")
    user_id = _current_user_id(client, headers)
    fixture_paths = ensure_default_fixtures()

    db = client._SessionLocal()
    try:
        from app.db.models import Organization
        org = Organization(name="印章分页测试企业")
        db.add(org)
        db.commit()
        db.refresh(org)
    finally:
        db.close()

    contract_id, _ = _create_contract_with_source_file(
        client, headers, org, fixture_paths[0], user_id
    )
    client.post(f"/api/seals/contracts/{contract_id}/extract", headers=headers)

    response = client.get(
        f"/api/seals/contracts/{contract_id}?page=1&size=1",
        headers=headers,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["size"] == 1
    assert data["total"] >= 1


def test_seal_detail_not_found(client):
    """不存在的印章 ID 应返回 404。"""
    headers = register_auth_headers(client, username="seal_detail_user", phone="13800138103")
    response = client.get("/api/seals/99999", headers=headers)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Phase 5 兼容性测试：旧路径 /api/v1/... 应 307 重定向到新路径 /api/seals/...
# ---------------------------------------------------------------------------


def test_old_extract_path_redirects():
    """旧路径 POST /api/v1/contracts/{cid}/seals/extract 应 307 到新路径。

    业务背景：Phase 5 迁移 prefix，旧路径保留 redirect 兼容至少一个版本周期。
    技术要点：307 保留 method（POST）与 body，query 一并透传。
    """
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/v1/contracts/123/seals/extract?dry_run=1",
            follow_redirects=False,
        )
        assert response.status_code == 307
        assert response.headers["location"] == (
            "/api/seals/contracts/123/extract?dry_run=1"
        )


def test_old_list_path_redirects():
    """旧路径 GET /api/v1/contracts/{cid}/seals 应 307 到新路径并保留 query。"""
    with TestClient(app) as test_client:
        response = test_client.get(
            "/api/v1/contracts/456/seals?page=2&size=5",
            follow_redirects=False,
        )
        assert response.status_code == 307
        assert response.headers["location"] == (
            "/api/seals/contracts/456?page=2&size=5"
        )


def test_old_detail_path_redirects():
    """旧路径 GET /api/v1/seals/{sid} 应 307 到 /api/seals/{sid}。"""
    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/seals/789", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/api/seals/789"


def test_old_extract_path_follows_redirect_to_auth_check():
    """跟随重定向后，未登录请求应落到新路径的鉴权校验返回 401。

    业务背景：redirect 兼容不能绕过鉴权；新路径仍执行 get_current_user。
    """
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/v1/contracts/1/seals/extract",
            follow_redirects=True,
        )
        assert response.status_code == 401
