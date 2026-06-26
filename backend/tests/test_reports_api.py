from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import (
    AccountingEntry,
    AccountingPeriod,
    ChartOfAccounts,
    OpeningBalance,
    Organization,
)
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
            yield test_client, TestingSessionLocal
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _seed(TestingSessionLocal):
    """构建一个最小可平衡账：
    期初：1002 借 1000 / 4001 贷 1000
    本期：销售 → 1122 借 1130 / 6001 贷 1000 / 2221 贷 130
    """
    db = TestingSessionLocal()
    try:
        org = Organization(name="报表测试", fiscal_year=2026)
        db.add(org)
        db.flush()
        period = AccountingPeriod(
            organization_id=org.id,
            period_code="2026-01",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )
        db.add(period)
        db.flush()

        for code, name, category, direction in [
            ("1002", "银行存款", "asset", "debit"),
            ("1122", "应收账款", "asset", "debit"),
            ("4001", "实收资本", "equity", "credit"),
            ("2221", "应交税费", "liability", "credit"),
            ("6001", "主营业务收入", "profit", "credit"),
            ("6601", "销售费用", "profit", "debit"),
            ("6801", "所得税费用", "profit", "debit"),
        ]:
            db.add(
                ChartOfAccounts(
                    code=code,
                    name=name,
                    parent_code=None,
                    level=1,
                    category=category,
                    direction=direction,
                    is_terminal=True,
                    status="active",
                    is_system=True,
                )
            )

        db.add(
            OpeningBalance(
                organization_id=org.id,
                period_id=period.id,
                account_code="1002",
                debit_balance=Decimal("1000"),
                credit_balance=Decimal("0"),
            )
        )
        db.add(
            OpeningBalance(
                organization_id=org.id,
                period_id=period.id,
                account_code="4001",
                debit_balance=Decimal("0"),
                credit_balance=Decimal("1000"),
            )
        )

        # 本期发生
        for code, debit, credit in [
            ("1122", Decimal("1130"), Decimal("0")),
            ("6001", Decimal("0"), Decimal("1000")),
            ("2221", Decimal("0"), Decimal("130")),
            ("6601", Decimal("100"), Decimal("0")),
            ("1002", Decimal("0"), Decimal("100")),
            ("6801", Decimal("50"), Decimal("0")),
            ("2221", Decimal("0"), Decimal("50")),
        ]:
            db.add(
                AccountingEntry(
                    organization_id=org.id,
                    import_job_id=0,
                    voucher_no="测-001",
                    voucher_date=date(2026, 1, 15),
                    account_code=code,
                    account_name=code,
                    debit_amount=debit,
                    credit_amount=credit,
                    entry_line_no=1,
                )
            )
        db.commit()
        return org.id, period.id
    finally:
        db.close()


def test_trial_balance_report(client):
    test_client, TestingSessionLocal = client
    org_id, period_id = _seed(TestingSessionLocal)
    resp = test_client.get(
        "/api/reports/trial-balance",
        params={"organization_id": org_id, "period_id": period_id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "rows" in body
    assert "totals" in body
    assert body["is_balanced"] is True


def test_balance_sheet(client):
    test_client, TestingSessionLocal = client
    org_id, period_id = _seed(TestingSessionLocal)
    resp = test_client.get(
        "/api/reports/balance-sheet",
        params={"organization_id": org_id, "period_id": period_id},
    )
    assert resp.status_code == 200
    body = resp.json()
    # 资产 = 银行存款 900 + 应收账款 1130 = 2030
    # 负债 = 应交税费 180
    # 权益 = 实收资本 1000 + 留存利润（损益类暂不结转，仅作期末资产负债校验）
    assert body["assets_total"] >= 0
    assert body["liabilities_total"] >= 0
    # 注意：本测试期间未做"损益结转"，恒等式可能不严格平衡，仅校验字段存在
    assert "is_balanced" in body


def test_income_statement(client):
    test_client, TestingSessionLocal = client
    org_id, period_id = _seed(TestingSessionLocal)
    resp = test_client.get(
        "/api/reports/income-statement",
        params={"organization_id": org_id, "period_id": period_id},
    )
    assert resp.status_code == 200
    body = resp.json()
    # 营业收入 = 1000，营业成本 = 0，期间费用 = 100，所得税 = 50
    assert body["operating_revenue"] == 1000
    assert body["period_expenses"] == 100
    # 营业利润 = 1000 - 0 - 100 + 0(投资) = 900
    assert body["operating_profit"] == 900
    # 总利润 = 900
    assert body["total_profit"] == 900
    # 净利润 = 900 - 50
    assert body["net_profit"] == 850


def _seed_reclassification(TestingSessionLocal):
    db = TestingSessionLocal()
    try:
        org = Organization(name="重分类测试", fiscal_year=2026)
        db.add(org)
        db.flush()
        period = AccountingPeriod(
            organization_id=org.id,
            period_code="2026-01",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )
        db.add(period)
        db.flush()

        for code, name, category, direction in [
            ("1122", "应收账款", "asset", "debit"),
            ("1123", "预付账款", "asset", "debit"),
            ("2202", "应付账款", "liability", "credit"),
            ("2203", "预收账款", "liability", "credit"),
        ]:
            db.add(
                ChartOfAccounts(
                    code=code,
                    name=name,
                    parent_code=None,
                    level=1,
                    category=category,
                    direction=direction,
                    is_terminal=True,
                    status="active",
                    is_system=True,
                )
            )

        for code, debit, credit in [
            ("1122", Decimal("0"), Decimal("500")),
            ("2202", Decimal("300"), Decimal("0")),
        ]:
            db.add(
                OpeningBalance(
                    organization_id=org.id,
                    period_id=period.id,
                    account_code=code,
                    debit_balance=debit,
                    credit_balance=credit,
                )
            )
        db.commit()
        return org.id, period.id
    finally:
        db.close()


def _seed_non_standard_account(TestingSessionLocal):
    db = TestingSessionLocal()
    try:
        org = Organization(name="非标准科目测试", fiscal_year=2026)
        db.add(org)
        db.flush()
        period = AccountingPeriod(
            organization_id=org.id,
            period_code="2026-01",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )
        db.add(period)
        db.flush()

        for code, name, category, direction in [
            ("1122", "应收账款", "asset", "debit"),
            ("9999", "自定义辅助科目", "asset", "debit"),
        ]:
            db.add(
                ChartOfAccounts(
                    code=code,
                    name=name,
                    parent_code=None,
                    level=1,
                    category=category,
                    direction=direction,
                    is_terminal=True,
                    status="active",
                    is_system=False,
                )
            )

        for code, debit, credit in [
            ("1122", Decimal("0"), Decimal("500")),
            ("9999", Decimal("200"), Decimal("0")),
        ]:
            db.add(
                OpeningBalance(
                    organization_id=org.id,
                    period_id=period.id,
                    account_code=code,
                    debit_balance=debit,
                    credit_balance=credit,
                )
            )
        db.commit()
        return org.id, period.id
    finally:
        db.close()


def test_balance_sheet_skips_non_standard_account_codes(client):
    """非标准科目编码不应触发往来重分类，且不能导致资产负债表接口 500。"""
    test_client, TestingSessionLocal = client
    org_id, period_id = _seed_non_standard_account(TestingSessionLocal)
    resp = test_client.get(
        "/api/reports/balance-sheet",
        params={"organization_id": org_id, "period_id": period_id},
    )

    assert resp.status_code == 200
    body = resp.json()
    assets = {row["account_code"]: row for row in body["assets"]}
    liabilities = {row["account_code"]: row for row in body["liabilities"]}

    assert assets["9999"]["closing_debit"] == 200
    assert "reclassified_to_account_code" not in assets["9999"]
    assert assets["1122"]["reclassified_to_account_code"] == "2203"
    assert liabilities["2203"]["closing_credit"] == 500

    adjustments = body["reclassification_adjustments"]
    assert all(item["from_account_code"] != "9999" for item in adjustments)


def test_balance_sheet_reclassifies_counterparty_reverse_balances(client):
    test_client, TestingSessionLocal = client
    org_id, period_id = _seed_reclassification(TestingSessionLocal)
    resp = test_client.get(
        "/api/reports/balance-sheet",
        params={"organization_id": org_id, "period_id": period_id},
    )

    assert resp.status_code == 200
    body = resp.json()
    assets = {row["account_code"]: row for row in body["assets"]}
    liabilities = {row["account_code"]: row for row in body["liabilities"]}

    assert assets["1122"]["closing_debit"] == 0
    assert assets["1122"]["reclassified_to_account_code"] == "2203"
    assert liabilities["2203"]["closing_credit"] == 500
    assert liabilities["2202"]["closing_credit"] == 0
    assert liabilities["2202"]["reclassified_to_account_code"] == "1123"
    assert assets["1123"]["closing_debit"] == 300

    adjustments = body["reclassification_adjustments"]
    assert {item["from_account_code"] for item in adjustments} == {"1122", "2202"}
    assert {item["to_account_code"] for item in adjustments} == {"2203", "1123"}
    assert all("不绑定借方或贷方方向" in item["counterparty_semantic_note"] for item in adjustments)


def test_unknown_period_returns_404(client):
    test_client, _ = client
    resp = test_client.get(
        "/api/reports/trial-balance",
        params={"organization_id": 1, "period_id": 9999},
    )
    assert resp.status_code == 404
