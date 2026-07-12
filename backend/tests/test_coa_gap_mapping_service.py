# -*- coding: utf-8 -*-
"""COA 缺口自动映射服务单元测试。"""
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
from app.services.accounting.coa_gap_mapping_service import (
    auto_provision_coa_gaps,
    resolve_coa_mapping_target,
    rollup_amount_map_with_gap_mapping,
    translate_legacy_code,
)
from app.services.accounting.financial_statements_service import balance_sheet, compute_account_balances
from app.services.shared.ledger_timeline_service import initialize_ledger_timeline


@pytest.fixture
def db():
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


def test_translate_legacy_equity_codes():
    assert translate_legacy_code("300102") == "400102"
    assert translate_legacy_code("3103") == "4103"
    assert translate_legacy_code("100202") == "100202"


def test_resolve_coa_mapping_target_legacy_equity():
    coa = {"1002", "4001", "4103"}
    target, source = resolve_coa_mapping_target("300102", coa)
    assert target == "4001"
    assert source in {"legacy_root", "legacy_prefix"}
    assert resolve_coa_mapping_target("3103", coa) == ("4103", "legacy_exact")
    assert resolve_coa_mapping_target("100202", coa) == ("1002", "prefix")


def test_rollup_amount_map_with_gap_mapping():
    coa = {"4001", "4103"}
    raw = {
        "300102": (Decimal("0"), Decimal("500000")),
        "300103": (Decimal("0"), Decimal("200000")),
        "3103": (Decimal("100"), Decimal("0")),
    }
    rolled, orphan_net, meta = rollup_amount_map_with_gap_mapping(raw, coa)
    assert rolled["4001"] == (Decimal("0"), Decimal("700000"))
    assert rolled["4103"] == (Decimal("100"), Decimal("0"))
    assert orphan_net == Decimal("0")
    assert meta["coa_gap_mapping_count"] == 3


def _seed_ledger_with_legacy_equity_entries(db):
    team = Team(name="COA缺口测试", type="firm")
    db.add(team)
    db.flush()

    ledger = Ledger(
        name="COA缺口测试账簿",
        team_id=team.id,
        status="active",
        accounting_start_date=date(2022, 1, 1),
    )
    db.add(ledger)
    db.flush()

    organization, period = initialize_ledger_timeline(db, ledger, organization_name="COA缺口测试")

    for code, name, category, direction in [
        ("1002", "银行存款", "asset", "debit"),
        ("4001", "实收资本", "equity", "credit"),
        ("4103", "本年利润", "equity", "credit"),
        ("2221", "应交税费", "liability", "credit"),
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
            debit_balance=Decimal("1000000"),
            credit_balance=Decimal("0"),
        )
    )
    db.add(
        OpeningBalance(
            organization_id=organization.id,
            ledger_id=ledger.id,
            period_id=period.id,
            account_code="300102",
            debit_balance=Decimal("0"),
            credit_balance=Decimal("700000"),
        )
    )

    for code, debit, credit in [
        ("1002", Decimal("0"), Decimal("100")),
        ("3103", Decimal("50"), Decimal("0")),
    ]:
        db.add(
            AccountingEntry(
                organization_id=organization.id,
                ledger_id=ledger.id,
                import_job_id=0,
                voucher_no="记-001",
                voucher_date=date(2022, 1, 15),
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


def test_compute_account_balances_rolls_legacy_equity_into_coa(db):
    ledger_id, period_id = _seed_ledger_with_legacy_equity_entries(db)

    rows = compute_account_balances(db, ledger_id, period_id)
    by_code = {row["account_code"]: row for row in rows}

    assert Decimal(by_code["4001"]["closing_credit"]) == Decimal("700000.00")
    assert Decimal(by_code["4103"]["closing_debit"]) == Decimal("50.00")

    report = balance_sheet(db, ledger_id, period_id)
    assert Decimal(report["unmapped_entry_net"]) == Decimal("0.00")
    assert report["coa_gap_mapping_count"] >= 1


def test_auto_provision_coa_gaps_dry_run(db):
    ledger_id, _ = _seed_ledger_with_legacy_equity_entries(db)
    result = auto_provision_coa_gaps(db, ledger_id, dry_run=True)
    assert "created_count" in result
    assert result["orphan_code_count"] >= 0


def test_auto_provision_inferred_orphan_asset_code(db):
    """孤儿资产科目（如 1604）应能按编码规则自动补全。"""
    team = Team(name="推断补全测试", type="firm")
    db.add(team)
    db.flush()
    ledger = Ledger(name="推断账簿", team_id=team.id, status="active", accounting_start_date=date(2022, 1, 1))
    db.add(ledger)
    db.flush()
    organization, period = initialize_ledger_timeline(db, ledger, organization_name="推断测试")
    for code, name, category, direction in [
        ("1002", "银行存款", "asset", "debit"),
        ("4001", "实收资本", "equity", "credit"),
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
        AccountingEntry(
            organization_id=organization.id,
            ledger_id=ledger.id,
            import_job_id=0,
            voucher_no="记-1604",
            voucher_date=date(2022, 6, 30),
            account_code="1604",
            account_name="在建工程",
            debit_amount=Decimal("1000"),
            credit_amount=Decimal("0"),
            entry_line_no=1,
            post_status="posted",
        )
    )
    db.add(
        AccountingEntry(
            organization_id=organization.id,
            ledger_id=ledger.id,
            import_job_id=0,
            voucher_no="记-1604",
            voucher_date=date(2022, 6, 30),
            account_code="4001",
            account_name="实收资本",
            debit_amount=Decimal("0"),
            credit_amount=Decimal("1000"),
            entry_line_no=2,
            post_status="posted",
        )
    )
    db.commit()

    result = auto_provision_coa_gaps(db, ledger.id, dry_run=False)
    assert result["created_count"] >= 1
    assert any(item.get("code") == "1604" for item in result["created"])

    report = balance_sheet(db, ledger.id, period.id)
    assert Decimal(report["unmapped_entry_net"]) == Decimal("0.00")
    assert report["is_balanced"]
