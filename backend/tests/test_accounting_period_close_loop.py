# -*- coding: utf-8 -*-
"""
会计期间闭环端到端测试。

业务场景：验证一个会计期间从凭证录入、复核、过账、损益结转、
        报表生成到结账的完整流程，确保财务逻辑正确。
创建日期：2026-07-03
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import AccountingPeriod, ChartOfAccounts, OpeningBalance, Organization
from app.db.session import Base, engine
from app.main import app
from app.models.ledger import Ledger
from app.models.team import Team
from app.models.user import User
from app.models.user_ledger_auth import UserLedgerAuth
from app.core.security import create_access_token


client = TestClient(app)


@pytest.fixture(scope="function")
def db_session():
    """测试用数据库会话，每次测试后重建表结构。"""
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
    """创建测试账簿、授权用户并初始化科目。"""
    from app.services.basic_data.coa_service import init_default_accounts

    ledger = Ledger(
        team_id=test_team.id,
        name="测试账簿",
        status="active",
        accounting_start_date=date(2024, 1, 1),
        organization_id=test_organization.id,
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
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def closed_loop_accounts(db_session, test_ledger, test_period):
    """初始化闭环测试所需的科目和期初余额。"""
    required_accounts = [
        ("1002", "银行存款", "asset", "debit"),
        ("4001", "实收资本", "equity", "credit"),
        ("6001", "主营业务收入", "profit", "credit"),
        ("6401", "主营业务成本", "profit", "debit"),
        ("4103", "本年利润", "equity", "credit"),
    ]
    for code, name, category, direction in required_accounts:
        existing = db_session.query(ChartOfAccounts).filter(
            ChartOfAccounts.ledger_id == test_ledger.id,
            ChartOfAccounts.code == code,
        ).first()
        if not existing:
            account = ChartOfAccounts(
                ledger_id=test_ledger.id,
                code=code,
                name=name,
                category=category,
                direction=direction,
                level=1,
                is_terminal=True,
                status="active",
            )
            db_session.add(account)

    # 期初余额：银行存款 10000，实收资本 10000
    db_session.add(OpeningBalance(
        organization_id=test_ledger.organization_id,
        ledger_id=test_ledger.id,
        period_id=test_period.id,
        account_code="1002",
        debit_balance=Decimal("10000.00"),
        credit_balance=Decimal("0.00"),
    ))
    db_session.add(OpeningBalance(
        organization_id=test_ledger.organization_id,
        ledger_id=test_ledger.id,
        period_id=test_period.id,
        account_code="4001",
        debit_balance=Decimal("0.00"),
        credit_balance=Decimal("10000.00"),
    ))
    db_session.commit()


class TestAccountingPeriodCloseLoop:
    """会计期间闭环测试。"""

    def test_close_period_auto_ensures_pl_transfer(
        self,
        db_session,
        test_ledger,
        test_organization,
        test_period,
        auth_headers,
        closed_loop_accounts,
    ):
        """未手工结转时，结账应自动尝试损益结转而非提示先点结转按钮。"""
        close_response = client.post(
            f"/api/accounting-periods/{test_period.id}/close",
            json={"operator": "test_accountant", "reason": "自动校验后结账"},
            headers=auth_headers,
        )
        detail = close_response.json().get("detail", "")
        assert "尚未结转损益" not in detail
        assert "请先执行损益结转" not in detail

    def test_full_period_close_loop(
        self,
        db_session,
        test_ledger,
        test_organization,
        test_period,
        auth_headers,
        closed_loop_accounts,
    ):
        """测试从凭证录入到结账的完整闭环。"""
        # 1. 录入销售凭证：借 银行存款 5000 / 贷 主营业务收入 5000
        voucher1_response = client.post(
            "/api/vouchers",
            json={
                "ledger_id": test_ledger.id,
                "organization_id": test_organization.id,
                "period_id": test_period.id,
                "voucher_type": "记",
                "voucher_number": "001",
                "voucher_date": "2024-01-15",
                "summary": "销售商品",
                "lines": [
                    {"line_no": 1, "account_code": "1002", "debit_amount": "5000.00", "credit_amount": "0.00", "summary": "银行存款"},
                    {"line_no": 2, "account_code": "6001", "debit_amount": "0.00", "credit_amount": "5000.00", "summary": "主营业务收入"},
                ],
            },
            headers=auth_headers,
        )
        assert voucher1_response.status_code == 201
        voucher1_id = voucher1_response.json()["data"]["voucher_id"]

        # 2. 录入成本凭证：借 主营业务成本 3000 / 贷 银行存款 3000
        voucher2_response = client.post(
            "/api/vouchers",
            json={
                "ledger_id": test_ledger.id,
                "organization_id": test_organization.id,
                "period_id": test_period.id,
                "voucher_type": "记",
                "voucher_number": "002",
                "voucher_date": "2024-01-20",
                "summary": "结转销售成本",
                "lines": [
                    {"line_no": 1, "account_code": "6401", "debit_amount": "3000.00", "credit_amount": "0.00", "summary": "主营业务成本"},
                    {"line_no": 2, "account_code": "1002", "debit_amount": "0.00", "credit_amount": "3000.00", "summary": "银行存款"},
                ],
            },
            headers=auth_headers,
        )
        assert voucher2_response.status_code == 201
        voucher2_id = voucher2_response.json()["data"]["voucher_id"]

        # 3. 复核并过账两张凭证
        for voucher_id in [voucher1_id, voucher2_id]:
            verify_response = client.post(f"/api/vouchers/{voucher_id}/verify", headers=auth_headers)
            assert verify_response.status_code == 200
            post_response = client.post(f"/api/vouchers/{voucher_id}/post", headers=auth_headers)
            assert post_response.status_code == 200
            assert post_response.json()["data"]["status"] == "posted"

        # 4. 执行损益结转
        pl_response = client.post(
            f"/api/accounting-periods/{test_period.id}/pl-transfer",
            headers=auth_headers,
        )
        assert pl_response.status_code == 200
        pl_data = pl_response.json()
        assert pl_data["status"] == "pl_transferred"
        assert pl_data["balance_sheet_balanced"] is True
        assert Decimal(pl_data["net_profit"]) == Decimal("2000.00")

        # 5. 生成三大报表并验证
        trial_balance = client.get(
            f"/api/reports/trial-balance?period_id={test_period.id}&ledger_id={test_ledger.id}",
            headers=auth_headers,
        )
        assert trial_balance.status_code == 200
        trial_data = trial_balance.json()
        print("trial balance rows:", [(r["account_code"], r["account_name"], r["period_debit"], r["period_credit"], r["closing_debit"], r["closing_credit"]) for r in trial_data["rows"]])
        assert trial_data["is_balanced"] is True

        balance_sheet = client.get(
            f"/api/reports/balance-sheet?period_id={test_period.id}&ledger_id={test_ledger.id}",
            headers=auth_headers,
        )
        assert balance_sheet.status_code == 200
        bs_data = balance_sheet.json()
        print("balance sheet:", bs_data.get("assets_total"), bs_data.get("liabilities_total"), bs_data.get("equity_total"))
        assert bs_data["is_balanced"] is True
        assert Decimal(bs_data["assets_total"]) == Decimal("12000.00")
        assert Decimal(bs_data["equity_total"]) == Decimal("12000.00")

        income_statement = client.get(
            f"/api/reports/income-statement?period_id={test_period.id}&ledger_id={test_ledger.id}",
            headers=auth_headers,
        )
        assert income_statement.status_code == 200
        is_data = income_statement.json()
        print("income statement:", is_data)
        assert Decimal(is_data["net_profit"]) == Decimal("2000.00")

        cash_flow = client.get(
            f"/api/reports/cash-flow-statement?period_id={test_period.id}&ledger_id={test_ledger.id}",
            headers=auth_headers,
        )
        assert cash_flow.status_code == 200
        cf_data = cash_flow.json()
        assert Decimal(cf_data["net_increase_in_cash"]) == Decimal("2000.00")

        # 6. 结账
        close_response = client.post(
            f"/api/accounting-periods/{test_period.id}/close",
            json={"operator": "test_accountant", "reason": "月末结账"},
            headers=auth_headers,
        )
        assert close_response.status_code == 200
        assert close_response.json()["status"] == "closed"
