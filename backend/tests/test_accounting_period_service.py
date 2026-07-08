from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import AccountingEntry, AccountingPeriod, ImportJob, Organization, PeriodCloseLog, PeriodSnapshot
from app.db.session import Base
from app.services.accounting.accounting_period_service import AccountingPeriodService


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

    period = AccountingPeriod(
        organization_id=organization.id,
        period_code="2026-01",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )
    db_session.add(period)
    db_session.flush()

    entries = [
        AccountingEntry(
            organization_id=organization.id,
            import_job_id=import_job.id,
            voucher_date=date(2026, 1, 5),
            account_code="6001",
            account_name="主营业务收入",
            entity_id=1,
            original_entity_name="主体A",
            debit_amount=Decimal("100.00"),
            credit_amount=Decimal("0.00"),
        ),
        AccountingEntry(
            organization_id=organization.id,
            import_job_id=import_job.id,
            voucher_date=date(2026, 1, 10),
            account_code="6001",
            account_name="主营业务收入",
            entity_id=1,
            original_entity_name="主体A",
            debit_amount=Decimal("0.00"),
            credit_amount=Decimal("30.00"),
        ),
        AccountingEntry(
            organization_id=organization.id,
            import_job_id=import_job.id,
            voucher_date=date(2026, 1, 20),
            account_code="1001",
            account_name="库存现金",
            entity_id=2,
            original_entity_name="主体B",
            debit_amount=Decimal("50.00"),
            credit_amount=Decimal("0.00"),
        ),
        AccountingEntry(
            organization_id=organization.id,
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


def prepare_period_for_close(db_session, period):
    """将期间设为已结转损益，满足结账前置条件。"""
    period.status = "pl_transferred"
    db_session.commit()
    db_session.refresh(period)
    return period


@pytest.fixture
def mock_balanced_balance_sheet(monkeypatch):
    """模拟资产负债表已平衡，供结账单元测试使用。"""
    monkeypatch.setattr(
        "app.services.accounting.financial_statements_service.balance_sheet",
        lambda db, ledger_id, period_id: {
            "is_balanced": True,
            "assets_total": "0",
            "liabilities_total": "0",
            "equity_total": "0",
        },
    )


def test_generate_period_snapshots_creates_valid_cny_snapshots(db_session):
    period = seed_period_entries(db_session)
    service = AccountingPeriodService(db_session)

    snapshots = service.generate_period_snapshots(period.id)

    assert service.get_latest_snapshot_version(period.id) == 1
    assert {snapshot.dimension_type for snapshot in snapshots} == {"account", "entity", "period_total"}
    assert all(snapshot.snapshot_status == "valid" for snapshot in snapshots)
    assert all(snapshot.currency == "CNY" for snapshot in snapshots)

    period_total = next(snapshot for snapshot in snapshots if snapshot.dimension_type == "period_total")
    assert period_total.amount == Decimal("120.00")
    assert period_total.source_scope["period_id"] == period.id
    assert period_total.generation_params["currency"] == "CNY"
    assert period_total.generation_params["foreign_currency_conversion"] is False

    account_snapshots = {snapshot.dimension_code: snapshot.amount for snapshot in snapshots if snapshot.dimension_type == "account"}
    assert account_snapshots == {"1001": Decimal("50.00"), "6001": Decimal("70.00")}


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
        "1001": Decimal("50.00"),
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
            "amount": Decimal("120.00"),
        }
    ]


def test_get_period_summary_uses_live_calculation_when_snapshot_missing(db_session):
    period = seed_period_entries(db_session)
    service = AccountingPeriodService(db_session)

    summary = service.get_period_summary(period.id, dimension_type="entity")

    assert summary["source"] == "live_calculation"
    assert summary["currency"] == "CNY"
    assert {item["dimension_id"]: item["amount"] for item in summary["items"]} == {
        1: Decimal("70.00"),
        2: Decimal("50.00"),
    }


def test_regenerate_period_snapshots_increments_version_and_invalidates_old_snapshots(db_session):
    period = seed_period_entries(db_session)
    service = AccountingPeriodService(db_session)

    first_snapshots = service.generate_period_snapshots(period.id, dimensions=["period_total"])
    second_snapshots = service.generate_period_snapshots(period.id, dimensions=["period_total"])

    assert [snapshot.snapshot_version for snapshot in first_snapshots] == [1]
    assert [snapshot.snapshot_version for snapshot in second_snapshots] == [2]
    assert service.get_latest_snapshot_version(period.id) == 2

    all_snapshots = (
        db_session.query(PeriodSnapshot)
        .filter(PeriodSnapshot.period_id == period.id)
        .order_by(PeriodSnapshot.snapshot_version)
        .all()
    )
    assert len(all_snapshots) == 2
    assert all_snapshots[0].snapshot_status == "invalidated"
    assert all_snapshots[0].invalidated_at is not None
    assert all_snapshots[1].snapshot_status == "valid"
    assert all(snapshot.currency == "CNY" for snapshot in all_snapshots)


def test_close_period_closes_period_and_creates_log(db_session, mock_balanced_balance_sheet):
    period = seed_period_entries(db_session)
    prepare_period_for_close(db_session, period)
    service = AccountingPeriodService(db_session)

    closed_period = service.close_period(period.id, operator="tester", reason="月结")

    assert closed_period.status == "closed"
    assert closed_period.closed_at is not None
    assert service.get_latest_snapshot_version(period.id) == 1

    log = db_session.query(PeriodCloseLog).filter(PeriodCloseLog.period_id == period.id).one()
    assert log.action_type == "close"
    assert log.old_status == "open"
    assert log.new_status == "closed"
    assert log.snapshot_version == 1
    assert log.operator == "tester"
    assert log.reason == "月结"
    assert log.transaction_id is not None


def test_close_period_fails_when_period_already_closed(db_session, mock_balanced_balance_sheet):
    period = seed_period_entries(db_session)
    prepare_period_for_close(db_session, period)
    service = AccountingPeriodService(db_session)
    service.close_period(period.id)

    with pytest.raises(ValueError, match="already closed"):
        service.close_period(period.id)

    logs = db_session.query(PeriodCloseLog).filter(PeriodCloseLog.period_id == period.id).all()
    assert len(logs) == 1


def test_reopen_period_reopens_period_invalidates_snapshot_and_creates_log(db_session, mock_balanced_balance_sheet):
    period = seed_period_entries(db_session)
    prepare_period_for_close(db_session, period)
    service = AccountingPeriodService(db_session)
    service.close_period(period.id)

    reopened_period = service.reopen_period(period.id, operator="auditor", reason="补录调整凭证")

    assert reopened_period.status == "reopened"
    assert reopened_period.reopened_at is not None
    assert reopened_period.updated_at == reopened_period.reopened_at

    snapshots = db_session.query(PeriodSnapshot).filter(PeriodSnapshot.period_id == period.id).all()
    assert snapshots
    assert all(snapshot.snapshot_status == "invalidated" for snapshot in snapshots)
    assert all(snapshot.invalidated_at is not None for snapshot in snapshots)

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
    period = seed_period_entries(db_session)
    service = AccountingPeriodService(db_session)

    with pytest.raises(ValueError, match="not closed"):
        service.reopen_period(period.id)

    db_session.expire_all()
    unchanged_period = db_session.get(AccountingPeriod, period.id)
    assert unchanged_period.status == "open"
    assert db_session.query(PeriodCloseLog).filter(PeriodCloseLog.period_id == period.id).count() == 0


def test_close_period_after_reopen_creates_new_valid_snapshot_version(db_session, mock_balanced_balance_sheet):
    period = seed_period_entries(db_session)
    prepare_period_for_close(db_session, period)
    service = AccountingPeriodService(db_session)
    service.close_period(period.id)
    service.reopen_period(period.id)

    reclosed_period = service.close_period(period.id, operator="tester", reason="重新月结")

    assert reclosed_period.status == "closed"
    assert service.get_latest_snapshot_version(period.id) == 2

    snapshots = (
        db_session.query(PeriodSnapshot)
        .filter(PeriodSnapshot.period_id == period.id)
        .order_by(PeriodSnapshot.snapshot_version)
        .all()
    )
    assert {snapshot.snapshot_status for snapshot in snapshots if snapshot.snapshot_version == 1} == {"invalidated"}
    assert {snapshot.snapshot_status for snapshot in snapshots if snapshot.snapshot_version == 2} == {"valid"}

    reclose_log = (
        db_session.query(PeriodCloseLog)
        .filter(PeriodCloseLog.period_id == period.id, PeriodCloseLog.action_type == "close")
        .order_by(PeriodCloseLog.id.desc())
        .first()
    )
    assert reclose_log.old_status == "reopened"
    assert reclose_log.new_status == "closed"
    assert reclose_log.snapshot_version == 2


def test_ensure_period_open_for_date_raises_for_closed_period_date(db_session, mock_balanced_balance_sheet):
    period = seed_period_entries(db_session)
    prepare_period_for_close(db_session, period)
    service = AccountingPeriodService(db_session)
    service.close_period(period.id)

    with pytest.raises(ValueError, match="closed"):
        service.ensure_period_open_for_date(period.organization_id, date(2026, 1, 15))

    service.ensure_period_open_for_date(period.organization_id, date(2026, 2, 1))


def test_close_period_rolls_back_when_snapshot_generation_fails(db_session, monkeypatch, mock_balanced_balance_sheet):
    period = seed_period_entries(db_session)
    prepare_period_for_close(db_session, period)
    service = AccountingPeriodService(db_session)

    def fail_generate_period_snapshots(period_id, dimensions=None, commit=True):
        raise RuntimeError("snapshot failed")

    monkeypatch.setattr(service, "generate_period_snapshots", fail_generate_period_snapshots)

    with pytest.raises(RuntimeError, match="snapshot failed"):
        service.close_period(period.id)

    db_session.expire_all()
    unchanged_period = db_session.get(AccountingPeriod, period.id)
    assert unchanged_period.status == "open"
    assert unchanged_period.closed_at is None
    assert db_session.query(PeriodSnapshot).filter(PeriodSnapshot.period_id == period.id).count() == 0
    assert db_session.query(PeriodCloseLog).filter(PeriodCloseLog.period_id == period.id).count() == 0


def test_close_period_rolls_back_partial_snapshot_when_transaction_fails(db_session, monkeypatch, mock_balanced_balance_sheet):
    period = seed_period_entries(db_session)
    prepare_period_for_close(db_session, period)
    service = AccountingPeriodService(db_session)

    def fail_after_partial_snapshot(period_id, dimensions=None, commit=True):
        partial_snapshot = PeriodSnapshot(
            organization_id=period.organization_id,
            period_id=period_id,
            snapshot_version=1,
            dimension_type="period_total",
            dimension_code="period_total",
            dimension_name="期间总计",
            amount=Decimal("120.00"),
            currency="CNY",
            source_scope={"period_id": period_id},
            generation_params={"currency": "CNY", "foreign_currency_conversion": False},
            snapshot_status="valid",
        )
        db_session.add(partial_snapshot)
        db_session.flush()
        raise RuntimeError("snapshot failed after partial write")

    monkeypatch.setattr(service, "generate_period_snapshots", fail_after_partial_snapshot)

    with pytest.raises(RuntimeError, match="snapshot failed after partial write"):
        service.close_period(period.id)

    db_session.expire_all()
    unchanged_period = db_session.get(AccountingPeriod, period.id)
    assert unchanged_period.status == "open"
    assert unchanged_period.closed_at is None
    assert db_session.query(PeriodSnapshot).filter(PeriodSnapshot.period_id == period.id).count() == 0
    assert db_session.query(PeriodCloseLog).filter(PeriodCloseLog.period_id == period.id).count() == 0
