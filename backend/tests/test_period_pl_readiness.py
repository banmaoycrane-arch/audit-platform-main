# -*- coding: utf-8 -*-
"""损益结转就绪校验：导入凭证已结转场景。"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import (
    AccountingEntry,
    AccountingPeriod,
    ChartOfAccounts,
    ImportJob,
    Organization,
    Voucher,
)
from app.db.session import Base
from app.models.ledger import Ledger
from app.models.team import Team
from app.services.accounting import period_close_service
from app.services.accounting.period_pl_health_service import assess_pl_transfer_readiness


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def _seed_imported_pl_closed_period(db_session):
    org = Organization(name="导入结转测试", fiscal_year=2026)
    db_session.add(org)
    db_session.flush()
    job = ImportJob(organization_id=org.id)
    db_session.add(job)
    db_session.flush()
    team = Team(name="团队")
    db_session.add(team)
    db_session.flush()
    ledger = Ledger(name="账簿", team_id=team.id, organization_id=org.id)
    db_session.add(ledger)
    db_session.flush()
    period = AccountingPeriod(
        organization_id=org.id,
        ledger_id=ledger.id,
        period_code="2026-01",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        status="open",
    )
    db_session.add(period)
    db_session.flush()
    for code, name, cat, direction in [
        ("1001", "库存现金", "asset", "debit"),
        ("6001", "主营业务收入", "profit", "credit"),
        ("4103", "本年利润", "equity", "credit"),
    ]:
        db_session.add(
            ChartOfAccounts(
                code=code,
                name=name,
                parent_code=None,
                level=1,
                category=cat,
                direction=direction,
                is_terminal=True,
                status="active",
                is_system=True,
                ledger_id=ledger.id,
            )
        )
    voucher = Voucher(
        organization_id=org.id,
        ledger_id=ledger.id,
        voucher_no="转-导入-001",
        voucher_date=date(2026, 1, 31),
        summary="期末损益结转",
        source_type="import",
        status="posted",
    )
    db_session.add(voucher)
    db_session.flush()
    entries = [
        ("1001", Decimal("100"), Decimal("0")),
        ("6001", Decimal("0"), Decimal("100")),
        ("6001", Decimal("100"), Decimal("0")),
        ("4103", Decimal("0"), Decimal("100")),
    ]
    for idx, (code, debit, credit) in enumerate(entries, start=1):
        db_session.add(
            AccountingEntry(
                organization_id=org.id,
                ledger_id=ledger.id,
                import_job_id=job.id,
                voucher_id=voucher.id,
                voucher_no=voucher.voucher_no,
                voucher_date=period.end_date,
                entry_line_no=idx,
                account_code=code,
                account_name=code,
                debit_amount=debit,
                credit_amount=credit,
                post_status="posted",
            )
        )
    db_session.commit()
    return ledger.id, period.id


def test_assess_pl_readiness_imported_satisfied(db_session):
    ledger_id, period_id = _seed_imported_pl_closed_period(db_session)
    assessment = assess_pl_transfer_readiness(db_session, ledger_id, period_id)
    assert assessment["ready"] is True
    assert assessment["mode"] == "imported_satisfied"
    assert assessment["profit_accounts_cleared"] is True
    assert assessment["can_close_without_manual_transfer"] is True


def test_ensure_pl_ready_marks_period_without_system_voucher(db_session):
    ledger_id, period_id = _seed_imported_pl_closed_period(db_session)
    result = period_close_service.ensure_pl_transfer_ready(db_session, ledger_id, period_id)
    assert result["mode"] == "imported_satisfied"
    period = db_session.get(AccountingPeriod, period_id)
    assert period.status == "pl_transferred"
    assert result.get("voucher_no") is None
