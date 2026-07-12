# -*- coding: utf-8 -*-
"""
模块功能：三大财务报表服务单元测试
业务场景：验证科目余额表、资产负债表、利润表的核心计算逻辑
政策依据：《企业会计准则》基本报表勾稽关系
输入数据：测试账簿、科目表、期初余额、会计分录
输出结果：报表计算结果与关键断言
创建日期：2026-07-03
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import AccountingEntry, AccountingPeriod, ChartOfAccounts, OpeningBalance
from app.db.session import Base
from app.models.ledger import Ledger
from app.models.team import Team
from app.services.accounting.financial_statements_service import (
    account_balance_breakdown,
    balance_sheet,
    compute_account_balances,
    income_statement,
    trial_balance_report,
)
from app.services.shared.ledger_timeline_service import initialize_ledger_timeline


@pytest.fixture
def db():
    """提供内存 SQLite 会话，并在用例结束后清理。"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _seed_minimal_ledger(db):
    """构建最小可平衡账簿：期初 + 本期销售与费用分录。"""
    team = Team(name="报表服务测试团队", type="firm")
    db.add(team)
    db.flush()

    ledger = Ledger(
        name="报表服务测试账簿",
        team_id=team.id,
        status="active",
        accounting_start_date=date(2026, 1, 1),
    )
    db.add(ledger)
    db.flush()

    organization, period = initialize_ledger_timeline(db, ledger, organization_name="报表服务测试")

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
                ledger_id=ledger.id,
            )
        )

    db.add(
        OpeningBalance(
            organization_id=organization.id,
            ledger_id=ledger.id,
            period_id=period.id,
            account_code="1002",
            debit_balance=Decimal("1000"),
            credit_balance=Decimal("0"),
        )
    )
    db.add(
        OpeningBalance(
            organization_id=organization.id,
            ledger_id=ledger.id,
            period_id=period.id,
            account_code="4001",
            debit_balance=Decimal("0"),
            credit_balance=Decimal("1000"),
        )
    )

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
                organization_id=organization.id,
                ledger_id=ledger.id,
                import_job_id=0,
                voucher_no="测-001",
                voucher_date=date(2026, 1, 15),
                account_code=code,
                account_name=code,
                debit_amount=debit,
                credit_amount=credit,
                entry_line_no=1,
                post_status="posted",
            )
        )

    db.commit()
    return ledger.id, period.id


def test_compute_account_balances_returns_all_accounts(db):
    """科目余额计算应返回所有科目，并包含期初、本期、期末六列。"""
    ledger_id, period_id = _seed_minimal_ledger(db)

    rows = compute_account_balances(db, ledger_id, period_id)

    codes = {row["account_code"] for row in rows}
    assert codes == {"1002", "1122", "4001", "2221", "6001", "6601", "6801"}
    for row in rows:
        assert "opening_debit" in row
        assert "period_debit" in row
        assert "closing_debit" in row


def test_trial_balance_report_is_balanced(db):
    """试算平衡表期末借贷合计必须相等。"""
    ledger_id, period_id = _seed_minimal_ledger(db)

    report = trial_balance_report(db, ledger_id, period_id)

    assert report["is_balanced"] is True
    assert Decimal(report["totals"]["closing_debit"]) == Decimal(
        report["totals"]["closing_credit"]
    )


def test_income_statement_calculation(db):
    """利润表应正确归集收入、费用并计算营业利润与净利润。"""
    ledger_id, period_id = _seed_minimal_ledger(db)

    report = income_statement(db, ledger_id, period_id)

    assert report["operating_revenue"] == "1000.00"
    assert report["period_expenses"] == "100.00"
    assert report["operating_profit"] == "900.00"
    assert report["total_profit"] == "900.00"
    assert report["income_tax"] == "50.00"
    assert report["net_profit"] == "850.00"


def test_balance_sheet_returns_category_totals(db):
    """资产负债表应正确区分资产、负债、权益类别并返回合计。"""
    ledger_id, period_id = _seed_minimal_ledger(db)

    report = balance_sheet(db, ledger_id, period_id)

    assert "assets" in report
    assert "liabilities" in report
    assert "equity" in report
    assert Decimal(report["assets_total"]) >= 0
    assert Decimal(report["liabilities_total"]) >= 0
    assert Decimal(report["equity_total"]) >= 0
    assert "is_balanced" in report


def test_account_balance_breakdown_returns_detail_codes(db):
    """汇总科目下钻应返回分录明细编码拆分余额。"""
    ledger_id, period_id = _seed_minimal_ledger(db)
    period = db.get(AccountingPeriod, period_id)
    assert period is not None

    for code, debit, credit in [
        ("100201", Decimal("50"), Decimal("0")),
        ("100202", Decimal("0"), Decimal("30")),
        ("1122", Decimal("0"), Decimal("20")),
    ]:
        db.add(
            AccountingEntry(
                organization_id=period.organization_id,
                ledger_id=ledger_id,
                import_job_id=0,
                voucher_no="测-002",
                voucher_date=date(2026, 1, 20),
                account_code=code,
                account_name=code,
                debit_amount=debit,
                credit_amount=credit,
                entry_line_no=1,
                post_status="posted",
            )
        )
    db.commit()

    breakdown = account_balance_breakdown(db, ledger_id, period_id, "1002")

    codes = {row["account_code"] for row in breakdown["rows"]}
    assert "100201" in codes
    assert "100202" in codes


def test_balance_sheet_net_movement_rolls_profit_into_4103(db):
    """净发生额视图应将损益类汇总进 4103，不在资产负债方单独列示。"""
    ledger_id, period_id = _seed_minimal_ledger(db)

    report = balance_sheet(db, ledger_id, period_id, presentation_mode="net_movement")

    assert report["presentation_mode"] == "net_movement"
    section_codes = {
        row["account_code"]
        for row in report["assets"] + report["liabilities"] + report["equity"]
    }
    assert "6001" not in section_codes
    assert "6601" not in section_codes
    assert "4103" in section_codes
    profit_row = next(row for row in report["equity"] if row["account_code"] == "4103")
    assert Decimal(profit_row["closing_credit"]) - Decimal(profit_row["closing_debit"]) == Decimal("850.00")


def test_trial_balance_report_includes_ytd_columns(db):
    """科目余额表应包含本年累计借贷发生额。"""
    ledger_id, period_id = _seed_minimal_ledger(db)

    report = trial_balance_report(db, ledger_id, period_id)
    assert report["rows"]
    assert "ytd_debit" in report["rows"][0]
    assert "ytd_credit" in report["rows"][0]
    assert "ytd_debit" in report["totals"]
    assert "ytd_credit" in report["totals"]


def test_trial_balance_report_includes_live_balance_meta(db):
    """开放期间报表应返回即时余额元数据。"""
    ledger_id, period_id = _seed_minimal_ledger(db)

    report = trial_balance_report(db, ledger_id, period_id)

    assert report["balance_source"] == "live"
    assert report["as_of_date"]
    assert report["period_id"] == period_id
