# -*- coding: utf-8 -*-
"""
Voucher 独立 CRUD API 单元测试。

业务场景：验证 /api/vouchers 接口的创建、查询、更新、删除、复核、入账能力。
创建日期：2026-07-01
"""
from decimal import Decimal
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import AccountingPeriod, Organization, Voucher
from app.db.session import Base, engine
from app.main import app
from app.models.user import User
from app.models.ledger import Ledger
from app.models.user_ledger_auth import UserLedgerAuth
from app.models.team import Team
from app.core.security import create_access_token


client = TestClient(app)


@pytest.fixture(scope="function")
def db_session():
    """测试用数据库会话。"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db_session):
    """创建测试用户。"""
    user = User(
        username="test_accountant",
        phone="13800000000",
        email="test@example.com",
        hashed_password="fake_hash",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_team(db_session):
    """创建测试团队。"""
    team = Team(name="测试团队", type="enterprise")
    db_session.add(team)
    db_session.commit()
    db_session.refresh(team)
    return team


@pytest.fixture
def test_organization(db_session):
    """创建测试组织。"""
    org = Organization(name="测试企业")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture
def test_ledger(db_session, test_team, test_user, test_organization):
    """创建测试账簿并授权用户。"""
    from app.services.basic_data.coa_service import init_default_accounts

    ledger = Ledger(
        team_id=test_team.id,
        name="测试账簿",
        status="active",
        accounting_start_date=date(2024, 1, 1),
    )
    db_session.add(ledger)
    db_session.commit()
    db_session.refresh(ledger)

    auth = UserLedgerAuth(
        user_id=test_user.id,
        ledger_id=ledger.id,
        role="accountant",
    )
    db_session.add(auth)
    db_session.flush()

    init_default_accounts(db_session, ledger.id)
    db_session.commit()
    return ledger


@pytest.fixture
def test_period(db_session, test_ledger, test_organization):
    """创建开放会计期间。"""
    period = AccountingPeriod(
        organization_id=test_organization.id,
        ledger_id=test_ledger.id,
        period_code="2024-01",
        period_type="monthly",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        status="open",
    )
    db_session.add(period)
    db_session.commit()
    db_session.refresh(period)
    return period


@pytest.fixture
def auth_headers(test_user):
    """生成认证请求头。"""
    token = create_access_token({"sub": str(test_user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    if test_user.last_ledger_id:
        headers["X-Ledger-Id"] = str(test_user.last_ledger_id)
    return headers


class TestVoucherCRUD:
    """凭证 CRUD 测试用例。"""

    def test_create_voucher_success(self, db_session, test_ledger, test_organization, test_period, auth_headers):
        """测试成功创建凭证。"""
        response = client.post(
            "/api/vouchers",
            json={
                "ledger_id": test_ledger.id,
                "organization_id": test_organization.id,
                "period_id": test_period.id,
                "voucher_type": "记",
                "voucher_number": "001",
                "voucher_date": "2024-01-15",
                "summary": "支付办公费",
                "attachment_count": 2,
                "lines": [
                    {"line_no": 1, "summary": "办公费", "account_code": "6602", "debit_amount": "1000.00", "credit_amount": "0.00"},
                    {"line_no": 2, "summary": "银行存款", "account_code": "1002", "debit_amount": "0.00", "credit_amount": "1000.00"},
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["voucher_no"] == "记-001"
        assert data["data"]["total_debit"] == "1000.00"
        assert data["data"]["total_credit"] == "1000.00"
        assert len(data["data"]["lines"]) == 2

    def test_create_voucher_unbalanced(self, db_session, test_ledger, test_organization, test_period, auth_headers):
        """测试借贷不平衡时拒绝创建。"""
        response = client.post(
            "/api/vouchers",
            json={
                "ledger_id": test_ledger.id,
                "organization_id": test_organization.id,
                "period_id": test_period.id,
                "voucher_type": "记",
                "voucher_number": "002",
                "voucher_date": "2024-01-15",
                "summary": "不平衡凭证",
                "lines": [
                    {"line_no": 1, "summary": "办公费", "account_code": "6602", "debit_amount": "1000.00", "credit_amount": "0.00"},
                    {"line_no": 2, "summary": "银行存款", "account_code": "1002", "debit_amount": "0.00", "credit_amount": "900.00"},
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "借贷不平衡" in response.json()["detail"]

    def test_create_voucher_duplicate_no(self, db_session, test_ledger, test_organization, test_period, auth_headers):
        """测试凭证号重复时拒绝。"""
        # 先创建第一张
        client.post(
            "/api/vouchers",
            json={
                "ledger_id": test_ledger.id,
                "organization_id": test_organization.id,
                "period_id": test_period.id,
                "voucher_type": "记",
                "voucher_number": "003",
                "voucher_date": "2024-01-15",
                "summary": "第一张",
                "lines": [
                    {"line_no": 1, "summary": "办公费", "account_code": "6602", "debit_amount": "1000.00", "credit_amount": "0.00"},
                    {"line_no": 2, "summary": "银行存款", "account_code": "1002", "debit_amount": "0.00", "credit_amount": "1000.00"},
                ],
            },
            headers=auth_headers,
        )
        # 再创建同号
        response = client.post(
            "/api/vouchers",
            json={
                "ledger_id": test_ledger.id,
                "organization_id": test_organization.id,
                "period_id": test_period.id,
                "voucher_type": "记",
                "voucher_number": "003",
                "voucher_date": "2024-01-20",
                "summary": "第二张",
                "lines": [
                    {"line_no": 1, "summary": "办公费", "account_code": "6602", "debit_amount": "500.00", "credit_amount": "0.00"},
                    {"line_no": 2, "summary": "银行存款", "account_code": "1002", "debit_amount": "0.00", "credit_amount": "500.00"},
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "已存在" in response.json()["detail"]

    def test_list_vouchers(self, db_session, test_ledger, test_organization, test_period, auth_headers):
        """测试查询凭证列表。"""
        # 创建凭证
        client.post(
            "/api/vouchers",
            json={
                "ledger_id": test_ledger.id,
                "organization_id": test_organization.id,
                "period_id": test_period.id,
                "voucher_type": "记",
                "voucher_number": "004",
                "voucher_date": "2024-01-15",
                "summary": "查询测试",
                "lines": [
                    {"line_no": 1, "summary": "办公费", "account_code": "6602", "debit_amount": "1000.00", "credit_amount": "0.00"},
                    {"line_no": 2, "summary": "银行存款", "account_code": "1002", "debit_amount": "0.00", "credit_amount": "1000.00"},
                ],
            },
            headers=auth_headers,
        )
        response = client.get(
            f"/api/vouchers?ledger_id={test_ledger.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_get_voucher_detail(self, db_session, test_ledger, test_organization, test_period, auth_headers):
        """测试查询凭证详情。"""
        create_response = client.post(
            "/api/vouchers",
            json={
                "ledger_id": test_ledger.id,
                "organization_id": test_organization.id,
                "period_id": test_period.id,
                "voucher_type": "记",
                "voucher_number": "005",
                "voucher_date": "2024-01-15",
                "summary": "详情测试",
                "lines": [
                    {"line_no": 1, "summary": "办公费", "account_code": "6602", "debit_amount": "1000.00", "credit_amount": "0.00"},
                    {"line_no": 2, "summary": "银行存款", "account_code": "1002", "debit_amount": "0.00", "credit_amount": "1000.00"},
                ],
            },
            headers=auth_headers,
        )
        voucher_id = create_response.json()["data"]["voucher_id"]
        response = client.get(
            f"/api/vouchers/{voucher_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["voucher_id"] == voucher_id
        assert len(data["data"]["lines"]) == 2

    def test_update_voucher_success(self, db_session, test_ledger, test_organization, test_period, auth_headers):
        """测试成功更新凭证。"""
        create_response = client.post(
            "/api/vouchers",
            json={
                "ledger_id": test_ledger.id,
                "organization_id": test_organization.id,
                "period_id": test_period.id,
                "voucher_type": "记",
                "voucher_number": "006",
                "voucher_date": "2024-01-15",
                "summary": "更新前",
                "lines": [
                    {"line_no": 1, "summary": "办公费", "account_code": "6602", "debit_amount": "1000.00", "credit_amount": "0.00"},
                    {"line_no": 2, "summary": "银行存款", "account_code": "1002", "debit_amount": "0.00", "credit_amount": "1000.00"},
                ],
            },
            headers=auth_headers,
        )
        voucher_id = create_response.json()["data"]["voucher_id"]
        response = client.put(
            f"/api/vouchers/{voucher_id}",
            json={
                "summary": "更新后",
                "lines": [
                    {"line_no": 1, "summary": "办公费-改", "account_code": "6602", "debit_amount": "2000.00", "credit_amount": "0.00"},
                    {"line_no": 2, "summary": "银行存款-改", "account_code": "1002", "debit_amount": "0.00", "credit_amount": "2000.00"},
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["summary"] == "更新后"
        assert data["data"]["total_debit"] == "2000.00"
        assert len(data["data"]["lines"]) == 2
        # 验证第一条分录摘要已更新
        assert data["data"]["lines"][0]["summary"] == "办公费-改"

    def test_delete_voucher_success(self, db_session, test_ledger, test_organization, test_period, auth_headers):
        """测试成功删除草稿凭证。"""
        create_response = client.post(
            "/api/vouchers",
            json={
                "ledger_id": test_ledger.id,
                "organization_id": test_organization.id,
                "period_id": test_period.id,
                "voucher_type": "记",
                "voucher_number": "007",
                "voucher_date": "2024-01-15",
                "summary": "删除测试",
                "lines": [
                    {"line_no": 1, "summary": "办公费", "account_code": "6602", "debit_amount": "1000.00", "credit_amount": "0.00"},
                    {"line_no": 2, "summary": "银行存款", "account_code": "1002", "debit_amount": "0.00", "credit_amount": "1000.00"},
                ],
            },
            headers=auth_headers,
        )
        voucher_id = create_response.json()["data"]["voucher_id"]
        response = client.delete(
            f"/api/vouchers/{voucher_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        # 验证已删除
        get_response = client.get(f"/api/vouchers/{voucher_id}", headers=auth_headers)
        assert get_response.status_code == 404

    def test_verify_and_post_voucher(self, db_session, test_ledger, test_organization, test_period, auth_headers):
        """测试凭证复核和入账流程。"""
        create_response = client.post(
            "/api/vouchers",
            json={
                "ledger_id": test_ledger.id,
                "organization_id": test_organization.id,
                "period_id": test_period.id,
                "voucher_type": "记",
                "voucher_number": "008",
                "voucher_date": "2024-01-15",
                "summary": "复核入账测试",
                "lines": [
                    {"line_no": 1, "summary": "办公费", "account_code": "6602", "debit_amount": "1000.00", "credit_amount": "0.00"},
                    {"line_no": 2, "summary": "银行存款", "account_code": "1002", "debit_amount": "0.00", "credit_amount": "1000.00"},
                ],
            },
            headers=auth_headers,
        )
        voucher_id = create_response.json()["data"]["voucher_id"]
        # 复核
        verify_response = client.post(
            f"/api/vouchers/{voucher_id}/verify",
            headers=auth_headers,
        )
        assert verify_response.status_code == 200
        assert verify_response.json()["data"]["status"] == "verified"
        # 入账
        post_response = client.post(
            f"/api/vouchers/{voucher_id}/post",
            headers=auth_headers,
        )
        assert post_response.status_code == 200
        assert post_response.json()["data"]["status"] == "posted"
        # 已入账不可删除
        delete_response = client.delete(f"/api/vouchers/{voucher_id}", headers=auth_headers)
        assert delete_response.status_code == 422

    def test_unauthorized_access(self, db_session, test_ledger, auth_headers):
        """测试无权访问账簿。"""
        # 使用另一个不存在的 ledger_id
        response = client.get(
            "/api/vouchers?ledger_id=999999",
            headers=auth_headers,
        )
        assert response.status_code == 403

