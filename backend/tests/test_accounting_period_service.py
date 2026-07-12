from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import AccountingEntry, AccountingPeriod, ChartOfAccounts, ImportJob, OpeningBalance, Organization, PeriodCloseLog, PeriodSnapshot
from app.db.session import Base
from app.models.ledger import Ledger
from app.models.team import Team
from app.services.accounting.accounting_period_service import AccountingPeriodService


def prepare_period_for_close(db_session, period: AccountingPeriod) -> AccountingPeriod:
    """测试辅助：补齐账簿并标记损益已结转，满足 close_period 前置条件。"""
    if not period.ledger_id:
        team = Team(name="期间测试团队")
        db_session.add(team)
        db_session.flush()
        ledger = Ledger(name="期间测试账簿", team_id=team.id, organization_id=period.organization_id)
        db_session.add(ledger)
        db_session.flush()
        period.ledger_id = ledger.id

    # 模拟损益已结转：将 6001 期末贷方余额转入 4103，使资产负债表可平衡结账
    from app.services.accounting import financial_statements_service

    if period.ledger_id is not None:
        report = financial_statements_service.trial_balance_report(
            db_session,
            period.ledger_id,
            period.id,
            as_of_date=period.end_date,
        )
        for row in report.get("rows", []):
            if row.get("_rollup_meta") or row.get("account_code") != "6001":
                continue
            closing_debit = Decimal(str(row["closing_debit"]))
            closing_credit = Decimal(str(row["closing_credit"]))
            if closing_credit > 0:
                db_session.add(
                    AccountingEntry(
                        organization_id=period.organization_id,
                        ledger_id=period.ledger_id,
                        import_job_id=1,
                        voucher_date=period.end_date,
                        voucher_no="转-期末-测试",
                        account_code="6001",
                        account_name="主营业务收入",
                        debit_amount=closing_credit,
                        credit_amount=Decimal("0.00"),
                    )
                )
                db_session.add(
                    AccountingEntry(
                        organization_id=period.organization_id,
                        ledger_id=period.ledger_id,
                        import_job_id=1,
                        voucher_date=period.end_date,
                        voucher_no="转-期末-测试",
                        account_code="4103",
                        account_name="本年利润",
                        debit_amount=Decimal("0.00"),
                        credit_amount=closing_credit,
                    )
                )
            elif closing_debit > 0:
                db_session.add(
                    AccountingEntry(
                        organization_id=period.organization_id,
                        ledger_id=period.ledger_id,
                        import_job_id=1,
                        voucher_date=period.end_date,
                        voucher_no="转-期末-测试",
                        account_code="4103",
                        account_name="本年利润",
                        debit_amount=closing_debit,
                        credit_amount=Decimal("0.00"),
                    )
                )
                db_session.add(
                    AccountingEntry(
                        organization_id=period.organization_id,
                        ledger_id=period.ledger_id,
                        import_job_id=1,
                        voucher_date=period.end_date,
                        voucher_no="转-期末-测试",
                        account_code="6001",
                        account_name="主营业务收入",
                        debit_amount=Decimal("0.00"),
                        credit_amount=closing_debit,
                    )
                )
            break

    period.status = "pl_transferred"
    db_session.commit()
    db_session.refresh(period)
    return period


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def seed_period_entries(db_session):
    organization = Organization(name="测试企业", fiscal_year=2026)
    db_session.add(organization)
    db_session.flush()

    import_job = ImportJob(organization_id=organization.id)
    db_session.add(import_job)
    db_session.flush()

    team = Team(name="期间测试团队")
    db_session.add(team)
    db_session.flush()

    ledger = Ledger(name="期间测试账簿", team_id=team.id, organization_id=organization.id)
    db_session.add(ledger)
    db_session.flush()

    period = AccountingPeriod(
        organization_id=organization.id,
        ledger_id=ledger.id,
        period_code="2026-01",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )
    db_session.add(period)
    db_session.flush()

    for code, name, category, direction in [
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
                category=category,
                direction=direction,
                is_terminal=True,
                status="active",
                is_system=True,
                ledger_id=ledger.id,
            )
        )

    entries = [
        AccountingEntry(
            organization_id=organization.id,
            ledger_id=ledger.id,
            import_job_id=import_job.id,
            voucher_date=date(2026, 1, 5),
            account_code="1001",
            account_name="库存现金",
            entity_id=1,
            original_entity_name="主体A",
            debit_amount=Decimal("120.00"),
            credit_amount=Decimal("0.00"),
        ),
        AccountingEntry(
            organization_id=organization.id,
            ledger_id=ledger.id,
            import_job_id=import_job.id,
            voucher_date=date(2026, 1, 5),
            account_code="6001",
            account_name="主营业务收入",
            entity_id=1,
            original_entity_name="主体A",
            debit_amount=Decimal("0.00"),
            credit_amount=Decimal("120.00"),
        ),
        AccountingEntry(
            organization_id=organization.id,
            ledger_id=ledger.id,
            import_job_id=import_job.id,
            voucher_date=date(2026, 1, 10),
            account_code="6001",
            account_name="主营业务收入",
            entity_id=1,
            original_entity_name="主体A",
            debit_amount=Decimal("50.00"),
            credit_amount=Decimal("0.00"),
        ),
        AccountingEntry(
            organization_id=organization.id,
            ledger_id=ledger.id,
            import_job_id=import_job.id,
            voucher_date=date(2026, 1, 10),
            account_code="1001",
            account_name="库存现金",
            entity_id=1,
            original_entity_name="主体A",
            debit_amount=Decimal("0.00"),
            credit_amount=Decimal("50.00"),
        ),
        AccountingEntry(
            organization_id=organization.id,
            ledger_id=ledger.id,
            import_job_id=import_job.id,
            voucher_date=date(2026, 2, 1),
            account_code="9999",
            account_name="期间外科目",
            entity_id=3,
            original_entity_name="主体C",
            debit_amount=Decimal("999.00"),
            credit_amount=Decimal("0.00"),
        ),
    ]
    db_session.add_all(entries)
    db_session.commit()
    db_session.refresh(period)
    return period


def test_generate_period_snapshots_creates_valid_cny_snapshots(db_session):
    period = seed_period_entries(db_session)
    service = AccountingPeriodService(db_session)

    snapshots = service.generate_period_snapshots(period.id)

    assert service.get_latest_snapshot_version(period.id) == 1
    assert {snapshot.dimension_type for snapshot in snapshots} == {"account", "entity", "period_total"}
    assert all(snapshot.snapshot_status == "valid" for snapshot in snapshots)
    assert all(snapshot.currency == "CNY" for snapshot in snapshots)

    period_total = next(snapshot for snapshot in snapshots if snapshot.dimension_type == "period_total")
    assert period_total.amount == Decimal("0.00")
    assert period_total.source_scope["period_id"] == period.id
    assert period_total.generation_params["currency"] == "CNY"
    assert period_total.generation_params["foreign_currency_conversion"] is False

    account_snapshots = {snapshot.dimension_code: snapshot.amount for snapshot in snapshots if snapshot.dimension_type == "account"}
    assert account_snapshots == {"1001": Decimal("70.00"), "6001": Decimal("70.00")}

    for snapshot in snapshots:
        if snapshot.dimension_type != "account":
            continue
        trial_row = snapshot.source_scope.get("trial_balance_row")
        assert trial_row is not None
        assert trial_row["account_code"] == snapshot.dimension_code
        assert "closing_debit" in trial_row
        assert "closing_credit" in trial_row
        assert "ytd_debit" in trial_row
        assert "ytd_credit" in trial_row
        assert snapshot.generation_params.get("snapshot_basis") == "trial_balance"


def test_get_period_summary_prefers_valid_snapshot(db_session):
    period = seed_period_entries(db_session)
    service = AccountingPeriodService(db_session)
    service.generate_period_snapshots(period.id, dimensions=["account"])

    db_session.add(
        AccountingEntry(
            organization_id=period.organization_id,
            import_job_id=1,
            voucher_date=date(2026, 1, 25),
            account_code="6001",
            account_name="主营业务收入",
            entity_id=1,
            original_entity_name="主体A",
            debit_amount=Decimal("999.00"),
            credit_amount=Decimal("0.00"),
        )
    )
    db_session.commit()

    summary = service.get_period_summary(period.id, dimension_type="account")

    assert summary["period_id"] == period.id
    assert summary["dimension_type"] == "account"
    assert summary["source"] == "snapshot"
    assert summary["currency"] == "CNY"
    assert {item["dimension_code"]: item["amount"] for item in summary["items"]} == {
        "1001": Decimal("70.00"),
        "6001": Decimal("70.00"),
    }
    assert all(
        {"dimension_type", "dimension_id", "dimension_code", "dimension_name", "amount"} <= set(item)
        for item in summary["items"]
    )


def test_get_period_summary_uses_live_calculation_when_snapshot_invalidated(db_session):
    period = seed_period_entries(db_session)
    service = AccountingPeriodService(db_session)
    service.generate_period_snapshots(period.id, dimensions=["period_total"])
    service.invalidate_period_snapshots(period.id)

    summary = service.get_period_summary(period.id)

    assert summary["period_id"] == period.id
    assert summary["dimension_type"] == "period_total"
    assert summary["source"] == "live_calculation"
    assert summary["currency"] == "CNY"
    assert summary["items"] == [
        {
            "dimension_type": "period_total",
            "dimension_id": None,
            "dimension_code": "period_total",
            "dimension_name": "期间总计",
            "amount": Decimal("0.00"),
        }
    ]


def test_get_period_summary_uses_live_calculation_when_snapshot_missing(db_session):
    period = seed_period_entries(db_session)
    service = AccountingPeriodService(db_session)

    summary = service.get_period_summary(period.id, dimension_type="entity")

    assert summary["source"] == "live_calculation"
    assert summary["currency"] == "CNY"
    assert {item["dimension_id"]: item["amount"] for item in summary["items"]} == {
        1: Decimal("0.00"),
    }


def test_regenerate_period_snapshots_replaces_previous_single_version(db_session):
    period = seed_period_entries(db_session)
    service = AccountingPeriodService(db_session)

    first_snapshots = service.generate_period_snapshots(period.id, dimensions=["period_total"])
    second_snapshots = service.generate_period_snapshots(period.id, dimensions=["period_total"])

    assert [snapshot.snapshot_version for snapshot in first_snapshots] == [1]
    assert [snapshot.snapshot_version for snapshot in second_snapshots] == [1]
    assert service.get_latest_snapshot_version(period.id) == 1

    all_snapshots = db_session.query(PeriodSnapshot).filter(PeriodSnapshot.period_id == period.id).all()
    assert len(all_snapshots) == 1
    assert all_snapshots[0].snapshot_status == "valid"
    assert all(snapshot.currency == "CNY" for snapshot in all_snapshots)


def test_generate_period_snapshots_rejects_closed_period(db_session):
    period = prepare_period_for_close(db_session, seed_period_entries(db_session))
    service = AccountingPeriodService(db_session)
    service.close_period(period.id)

    with pytest.raises(ValueError, match="已结账期间不可重新生成"):
        service.generate_period_snapshots(period.id)


def test_close_period_carries_forward_opening_balances_to_next_period(db_session):
    period = prepare_period_for_close(db_session, seed_period_entries(db_session))
    next_period = AccountingPeriod(
        organization_id=period.organization_id,
        ledger_id=period.ledger_id,
        period_code="2026-02",
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
    )
    db_session.add(next_period)
    db_session.commit()

    service = AccountingPeriodService(db_session)
    service.close_period(period.id)

    opening_rows = (
        db_session.query(OpeningBalance)
        .filter(OpeningBalance.period_id == next_period.id)
        .order_by(OpeningBalance.account_code)
        .all()
    )
    opening_map = {
        row.account_code: (row.debit_balance, row.credit_balance)
        for row in opening_rows
    }
    assert opening_map["1001"] == (Decimal("70.00"), Decimal("0.00"))
    assert opening_map["4103"] == (Decimal("0.00"), Decimal("70.00"))
    assert all("承接自已结账期间" in (row.notes or "") for row in opening_rows)


def test_close_period_closes_period_and_creates_log(db_session):
    period = prepare_period_for_close(db_session, seed_period_entries(db_session))
    service = AccountingPeriodService(db_session)

    closed_period = service.close_period(period.id, operator="tester", reason="月结")

    assert closed_period.status == "closed"
    assert closed_period.closed_at is not None
    assert service.get_latest_snapshot_version(period.id) == 1

    log = db_session.query(PeriodCloseLog).filter(PeriodCloseLog.period_id == period.id).one()
    assert log.action_type == "close"
    assert log.old_status == "pl_transferred"
    assert log.new_status == "closed"
    assert log.snapshot_version == 1
    assert log.operator == "tester"
    assert log.reason == "月结"
    assert log.transaction_id is not None


def test_close_period_fails_when_period_already_closed(db_session):
    period = prepare_period_for_close(db_session, seed_period_entries(db_session))
    service = AccountingPeriodService(db_session)
    service.close_period(period.id)

    with pytest.raises(ValueError, match="already closed"):
        service.close_period(period.id)

    logs = db_session.query(PeriodCloseLog).filter(PeriodCloseLog.period_id == period.id).all()
    assert len(logs) == 1


def test_reopen_period_reopens_period_purges_snapshot_and_creates_log(db_session):
    period = prepare_period_for_close(db_session, seed_period_entries(db_session))
    service = AccountingPeriodService(db_session)
    service.close_period(period.id)

    reopened_period = service.reopen_period(period.id, operator="auditor", reason="补录调整凭证")

    assert reopened_period.status == "reopened"
    assert reopened_period.reopened_at is not None
    assert reopened_period.updated_at == reopened_period.reopened_at

    snapshots = db_session.query(PeriodSnapshot).filter(PeriodSnapshot.period_id == period.id).all()
    assert snapshots == []
    assert service.get_latest_snapshot_version(period.id) == 0

    reopen_log = (
        db_session.query(PeriodCloseLog)
        .filter(PeriodCloseLog.period_id == period.id, PeriodCloseLog.action_type == "reopen")
        .one()
    )
    assert reopen_log.old_status == "closed"
    assert reopen_log.new_status == "reopened"
    assert reopen_log.snapshot_version == 1
    assert reopen_log.operator == "auditor"
    assert reopen_log.reason == "补录调整凭证"
    assert reopen_log.transaction_id is not None


def test_reopen_period_fails_when_period_is_not_closed(db_session):
    period = prepare_period_for_close(db_session, seed_period_entries(db_session))
    service = AccountingPeriodService(db_session)

    with pytest.raises(ValueError, match="not closed"):
        service.reopen_period(period.id)

    db_session.expire_all()
    unchanged_period = db_session.get(AccountingPeriod, period.id)
    assert unchanged_period.status == "pl_transferred"
    assert db_session.query(PeriodCloseLog).filter(PeriodCloseLog.period_id == period.id).count() == 0


def test_close_period_after_reopen_replaces_single_snapshot(db_session):
    period = prepare_period_for_close(db_session, seed_period_entries(db_session))
    service = AccountingPeriodService(db_session)
    service.close_period(period.id)
    service.reopen_period(period.id)

    reclosed_period = service.close_period(period.id, operator="tester", reason="重新月结")

    assert reclosed_period.status == "closed"
    assert service.get_latest_snapshot_version(period.id) == 1

    snapshots = db_session.query(PeriodSnapshot).filter(PeriodSnapshot.period_id == period.id).all()
    assert len(snapshots) >= 1
    assert all(snapshot.snapshot_version == 1 for snapshot in snapshots)
    assert all(snapshot.snapshot_status == "valid" for snapshot in snapshots)

    reclose_log = (
        db_session.query(PeriodCloseLog)
        .filter(PeriodCloseLog.period_id == period.id, PeriodCloseLog.action_type == "close")
        .order_by(PeriodCloseLog.id.desc())
        .first()
    )
    assert reclose_log.old_status == "reopened"
    assert reclose_log.new_status == "closed"
    assert reclose_log.snapshot_version == 1


def test_closed_period_trial_balance_reads_frozen_snapshot(db_session):
    period = prepare_period_for_close(db_session, seed_period_entries(db_session))
    service = AccountingPeriodService(db_session)
    service.close_period(period.id)

    from app.services.accounting.financial_statements_service import trial_balance_report

    report = trial_balance_report(db_session, period.ledger_id, period.id)
    assert report["balance_source"] == "snapshot"
    assert report.get("snapshot_frozen") is True
    assert report["rows"]
    assert "ytd_debit" in report["rows"][0]
    assert "ytd_credit" in report["rows"][0]


def test_ensure_period_open_for_date_raises_for_closed_period_date(db_session):
    period = prepare_period_for_close(db_session, seed_period_entries(db_session))
    service = AccountingPeriodService(db_session)
    service.close_period(period.id)

    with pytest.raises(ValueError, match="closed"):
        service.ensure_period_open_for_date(period.organization_id, date(2026, 1, 15))

    service.ensure_period_open_for_date(period.organization_id, date(2026, 2, 1))


def test_close_period_rolls_back_when_snapshot_generation_fails(db_session, monkeypatch):
    period = prepare_period_for_close(db_session, seed_period_entries(db_session))
    service = AccountingPeriodService(db_session)

    def fail_create_close_snapshots(period_id):
        raise RuntimeError("snapshot failed")

    monkeypatch.setattr(service, "_create_close_snapshots", fail_create_close_snapshots)

    with pytest.raises(RuntimeError, match="snapshot failed"):
        service.close_period(period.id)

    db_session.expire_all()
    unchanged_period = db_session.get(AccountingPeriod, period.id)
    assert unchanged_period.status == "pl_transferred"
    assert unchanged_period.closed_at is None
    assert db_session.query(PeriodSnapshot).filter(PeriodSnapshot.period_id == period.id).count() == 0
    assert db_session.query(PeriodCloseLog).filter(PeriodCloseLog.period_id == period.id).count() == 0


def test_close_period_rolls_back_partial_snapshot_when_transaction_fails(db_session, monkeypatch):
    period = prepare_period_for_close(db_session, seed_period_entries(db_session))
    service = AccountingPeriodService(db_session)

    def fail_after_partial_snapshot(period_id):
        partial_snapshot = PeriodSnapshot(
            organization_id=period.organization_id,
            period_id=period_id,
            snapshot_version=1,
            dimension_type="account",
            dimension_code="1001",
            dimension_name="库存现金",
            amount=Decimal("70.00"),
            currency="CNY",
            source_scope={"period_id": period_id, "trial_balance_row": {"account_code": "1001"}},
            generation_params={"currency": "CNY", "snapshot_basis": "trial_balance"},
            snapshot_status="valid",
        )
        db_session.add(partial_snapshot)
        db_session.flush()
        raise RuntimeError("snapshot failed after partial write")

    monkeypatch.setattr(service, "_create_close_snapshots", fail_after_partial_snapshot)

    with pytest.raises(RuntimeError, match="snapshot failed after partial write"):
        service.close_period(period.id)

    db_session.expire_all()
    unchanged_period = db_session.get(AccountingPeriod, period.id)
    assert unchanged_period.status == "pl_transferred"
    assert unchanged_period.closed_at is None
    assert db_session.query(PeriodSnapshot).filter(PeriodSnapshot.period_id == period.id).count() == 0
    assert db_session.query(PeriodCloseLog).filter(PeriodCloseLog.period_id == period.id).count() == 0
