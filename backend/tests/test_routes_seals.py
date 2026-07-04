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
    response = client.post("/api/v1/contracts/1/seals/extract")
    assert response.status_code == 401


def _current_user_id(client, headers):
    """通过 /api/auth/me 获取当前登录用户 ID。"""
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    return response.json()["id"]


def test_extract_seals_for_nonexistent_contract(client):
    """合同不存在应返回 404。"""
    headers = register_auth_headers(client, username="seal_extract_user_1", phone="13800138100")
    response = client.post("/api/v1/contracts/99999/seals/extract", headers=headers)
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
        f"/api/v1/contracts/{contract_id}/seals/extract",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["contract_id"] == contract_id
    assert data["extracted_count"] >= 1
    assert len(data["seals"]) == data["extracted_count"]

    # 列表接口校验
    list_response = client.get(
        f"/api/v1/contracts/{contract_id}/seals?page=1&size=10",
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
    detail_response = client.get(f"/api/v1/seals/{seal_id}", headers=headers)
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
    client.post(f"/api/v1/contracts/{contract_id}/seals/extract", headers=headers)

    response = client.get(
        f"/api/v1/contracts/{contract_id}/seals?page=1&size=1",
        headers=headers,
    )
    data = response.json()
    assert response.status_code == 200
    assert data["size"] == 1
    assert data["total"] >= 1


def test_seal_detail_not_found(client):
    """不存在的印章 ID 应返回 404。"""
    headers = register_auth_headers(client, username="seal_detail_user", phone="13800138103")
    response = client.get("/api/v1/seals/99999", headers=headers)
    assert response.status_code == 404
