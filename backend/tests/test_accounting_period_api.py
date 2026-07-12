from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import AccountingEntry, ChartOfAccounts, ImportJob, Organization
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
            test_client.test_engine = engine
            yield test_client, TestingSessionLocal
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def seed_organization_with_entries(TestingSessionLocal):
    db = TestingSessionLocal()
    try:
        organization = Organization(name="API测试企业", fiscal_year=2026)
        db.add(organization)
        db.flush()
        import_job = ImportJob(organization_id=organization.id)
        db.add(import_job)
        db.flush()
        db.add_all(
            [
                AccountingEntry(
                    organization_id=organization.id,
                    import_job_id=import_job.id,
                    voucher_date=date(2026, 1, 5),
                    account_code="1001",
                    account_name="库存现金",
                    debit_amount=Decimal("100.00"),
                    credit_amount=Decimal("0.00"),
                ),
                AccountingEntry(
                    organization_id=organization.id,
                    import_job_id=import_job.id,
                    voucher_date=date(2026, 1, 5),
                    account_code="6001",
                    account_name="主营业务收入",
                    debit_amount=Decimal("0.00"),
                    credit_amount=Decimal("100.00"),
                ),
            ]
        )
        db.commit()
        return organization.id
    finally:
        db.close()


def test_accounting_period_list_returns_business_error_when_schema_is_incomplete(client):
    test_client, _ = client

    with test_client.test_engine.begin() as connection:
        connection.execute(text("DROP TABLE accounting_periods"))

    response = test_client.get("/api/accounting-periods")
    assert response.status_code == 422
    assert "会计期间加载失败" in response.json()["detail"]


def test_accounting_period_api_create_close_reopen_and_summary_source(client):
    test_client, TestingSessionLocal = client
    organization_id = seed_organization_with_entries(TestingSessionLocal)

    create_response = test_client.post(
        "/api/accounting-periods",
        json={
            "organization_id": organization_id,
            "period_code": "2026-01",
            "period_type": "monthly",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
        },
    )
    assert create_response.status_code == 200
    created_period = create_response.json()
    assert created_period["status"] == "open"
    assert created_period["snapshot_status"] is None
    assert created_period["snapshot_version"] == 0
    assert created_period["source"] == "live_calculation"
    period_id = created_period["id"]

    live_summary_response = test_client.get(f"/api/accounting-periods/{period_id}/summary?dimension_type=period_total")
    assert live_summary_response.status_code == 200
    live_summary = live_summary_response.json()
    assert live_summary["source"] == "live_calculation"
    assert live_summary["period_status"] == "open"
    assert live_summary["snapshot_status"] is None
    assert live_summary["snapshot_version"] == 0

    db = TestingSessionLocal()
    try:
        from app.db.models import AccountingPeriod
        from app.models.ledger import Ledger
        from app.models.team import Team

        period = db.get(AccountingPeriod, period_id)
        import_job = db.query(ImportJob).filter(ImportJob.organization_id == organization_id).first()
        import_job_id = import_job.id if import_job else 1
        team = Team(name="API期间测试团队")
        db.add(team)
        db.flush()
        ledger = Ledger(name="API期间测试账簿", team_id=team.id, organization_id=organization_id)
        db.add(ledger)
        db.flush()
        period.ledger_id = ledger.id

        for code, name, category, direction in [
            ("1001", "库存现金", "asset", "debit"),
            ("6001", "主营业务收入", "profit", "credit"),
            ("4103", "本年利润", "equity", "credit"),
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

        for entry in db.query(AccountingEntry).filter(AccountingEntry.organization_id == organization_id).all():
            entry.ledger_id = ledger.id

        db.add(
            AccountingEntry(
                organization_id=organization_id,
                ledger_id=ledger.id,
                import_job_id=import_job_id,
                voucher_date=period.end_date,
                voucher_no="转-期末-API",
                account_code="6001",
                account_name="主营业务收入",
                debit_amount=Decimal("100.00"),
                credit_amount=Decimal("0.00"),
            )
        )
        db.add(
            AccountingEntry(
                organization_id=organization_id,
                ledger_id=ledger.id,
                import_job_id=import_job_id,
                voucher_date=period.end_date,
                voucher_no="转-期末-API",
                account_code="4103",
                account_name="本年利润",
                debit_amount=Decimal("0.00"),
                credit_amount=Decimal("100.00"),
            )
        )

        period.status = "pl_transferred"
        db.commit()
    finally:
        db.close()

    close_response = test_client.post(
        f"/api/accounting-periods/{period_id}/close",
        json={"operator": "tester", "reason": "月结"},
    )
    assert close_response.status_code == 200
    closed_period = close_response.json()
    assert closed_period["status"] == "closed"
    assert closed_period["snapshot_status"] == "valid"
    assert closed_period["snapshot_version"] == 1
    assert closed_period["source"] == "snapshot"

    snapshot_summary_response = test_client.get(f"/api/accounting-periods/{period_id}/summary?dimension_type=period_total")
    assert snapshot_summary_response.status_code == 200
    snapshot_summary = snapshot_summary_response.json()
    assert snapshot_summary["source"] == "snapshot"
    assert snapshot_summary["period_status"] == "closed"
    assert snapshot_summary["snapshot_status"] == "valid"
    assert snapshot_summary["snapshot_version"] == 1

    reopen_response = test_client.post(
        f"/api/accounting-periods/{period_id}/reopen",
        json={"operator": "auditor", "reason": "补录调整凭证"},
    )
    assert reopen_response.status_code == 200
    reopened_period = reopen_response.json()
    assert reopened_period["status"] == "reopened"
    assert reopened_period["snapshot_status"] is None
    assert reopened_period["snapshot_version"] == 0
    assert reopened_period["source"] == "live_calculation"

    reopened_summary_response = test_client.get(f"/api/accounting-periods/{period_id}/summary?dimension_type=period_total")
    assert reopened_summary_response.status_code == 200
    reopened_summary = reopened_summary_response.json()
    assert reopened_summary["source"] == "live_calculation"
    assert reopened_summary["period_status"] == "reopened"
    assert reopened_summary["snapshot_status"] is None
    assert reopened_summary["snapshot_version"] == 0


def test_accounting_period_recommendation_matches_open_period_and_suggests_month(client):
    test_client, TestingSessionLocal = client
    organization_id = seed_organization_with_entries(TestingSessionLocal)

    create_response = test_client.post(
        "/api/accounting-periods",
        json={
            "organization_id": organization_id,
            "period_code": "2026-06",
            "period_type": "monthly",
            "start_date": "2026-06-01",
            "end_date": "2026-06-30",
        },
    )
    assert create_response.status_code == 200

    matched_response = test_client.get(
        f"/api/accounting-periods/recommendation?organization_id={organization_id}&target_date=2026-06-18"
    )
    assert matched_response.status_code == 200
    matched_payload = matched_response.json()
    assert matched_payload["matched_period"]["period_code"] == "2026-06"
    assert matched_payload["suggested_period"] is None

    suggested_response = test_client.get(
        f"/api/accounting-periods/recommendation?organization_id={organization_id}&target_date=2026-07-03&period_type=monthly"
    )
    assert suggested_response.status_code == 200
    suggested_payload = suggested_response.json()
    assert suggested_payload["matched_period"] is None
    assert suggested_payload["suggested_period"]["period_code"] == "2026-07"
    assert suggested_payload["suggested_period"]["start_date"] == "2026-07-01"
    assert suggested_payload["suggested_period"]["end_date"] == "2026-07-31"


def test_accounting_period_api_list_and_create_snapshot(client):
    test_client, TestingSessionLocal = client
    organization_id = seed_organization_with_entries(TestingSessionLocal)

    create_response = test_client.post(
        "/api/accounting-periods",
        json={
            "organization_id": organization_id,
            "period_code": "2026-02",
            "start_date": "2026-02-01",
            "end_date": "2026-02-28",
        },
    )
    assert create_response.status_code == 200
    period_id = create_response.json()["id"]

    snapshot_response = test_client.post(
        f"/api/accounting-periods/{period_id}/snapshots",
        json={"dimensions": ["period_total"]},
    )
    assert snapshot_response.status_code == 200
    snapshot_payload = snapshot_response.json()
    assert snapshot_payload["period"]["status"] == "open"
    assert snapshot_payload["period"]["snapshot_status"] == "valid"
    assert snapshot_payload["period"]["snapshot_version"] == 1
    assert snapshot_payload["period"]["source"] == "snapshot"
    assert snapshot_payload["snapshots"][0]["snapshot_status"] == "valid"

    list_response = test_client.get(f"/api/accounting-periods?organization_id={organization_id}")
    assert list_response.status_code == 200
    periods = list_response.json()
    assert len(periods) == 1
    assert periods[0]["period_code"] == "2026-02"
    assert periods[0]["status"] == "open"
    assert periods[0]["snapshot_status"] == "valid"
    assert periods[0]["snapshot_version"] == 1
