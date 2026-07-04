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
from app.models.ledger import Ledger
from app.models.team import Team
from app.models.user import User
from app.services.shared.ledger_management_service import create_ledger
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
    """期初平衡 + 本期收入1000 / 费用100 / 所得税50 → 净利润 850"""
    db = TestingSessionLocal()
    try:
        team = Team(name="结转测试团队", type="virtual")
        db.add(team)
        db.flush()

        user = User(username="结转测试用户", phone="13800000006", team_id=team.id)
        db.add(user)
        db.flush()

        ledger = create_ledger(
            db,
            team_id=team.id,
            name="结转测试账簿",
            accounting_start_date=date(2026, 1, 1),
        )
        db.flush()

        period = db.query(AccountingPeriod).filter(
            AccountingPeriod.ledger_id == ledger.id,
            AccountingPeriod.period_code == "2026-01",
        ).first()

        org_id = period.organization_id

        db.add(OpeningBalance(
            organization_id=org_id, ledger_id=ledger.id, period_id=period.id,
            account_code="1002", debit_balance=Decimal("1000"), credit_balance=Decimal("0"),
        ))
        db.add(OpeningBalance(
            organization_id=org_id, ledger_id=ledger.id, period_id=period.id,
            account_code="4001", debit_balance=Decimal("0"), credit_balance=Decimal("1000"),
        ))

        # 本期发生（手工编排：收入 1000 / 费用 100 / 所得税 50）
        for code, debit, credit in [
            ("1122", Decimal("1130"), Decimal("0")),
            ("6001", Decimal("0"), Decimal("1000")),
            ("2221", Decimal("0"), Decimal("130")),
            ("6601", Decimal("100"), Decimal("0")),
            ("1002", Decimal("0"), Decimal("100")),
            ("6801", Decimal("50"), Decimal("0")),
            ("2221", Decimal("0"), Decimal("50")),
        ]:
            db.add(AccountingEntry(
                ledger_id=ledger.id, organization_id=org_id,
                import_job_id=0, voucher_no="测-001", voucher_date=date(2026, 1, 15),
                account_code=code, account_name=code,
                debit_amount=debit, credit_amount=credit,
                entry_line_no=1,
            ))
        db.commit()
        return org_id, period.id
    finally:
        db.close()


def test_pl_transfer_makes_balance_sheet_balanced(client):
    test_client, TestingSessionLocal = client
    org_id, period_id = _seed(TestingSessionLocal)

    # 结转前不平衡
    bs_before = test_client.get(
        "/api/reports/balance-sheet",
        params={"organization_id": org_id, "period_id": period_id},
    ).json()
    assert bs_before["is_balanced"] is False

    # 执行结转
    transfer = test_client.post(f"/api/accounting-periods/{period_id}/pl-transfer")
    if transfer.status_code != 200:
        print(f"Transfer error: {transfer.status_code} - {transfer.json()}")
    assert transfer.status_code == 200
    body = transfer.json()
    assert body["status"] == "pl_transferred"
    assert body["lines"] > 0
    # 净利润 = 1000 - 100 - 50 = 850
    assert body["net_profit"] == 850

    # 结转后资产负债表平衡
    bs_after = test_client.get(
        "/api/reports/balance-sheet",
        params={"organization_id": org_id, "period_id": period_id},
    ).json()
    assert bs_after["is_balanced"] is True


def test_pl_transfer_idempotent_blocked_until_reversed(client):
    test_client, TestingSessionLocal = client
    org_id, period_id = _seed(TestingSessionLocal)

    test_client.post(f"/api/accounting-periods/{period_id}/pl-transfer")

    second = test_client.post(f"/api/accounting-periods/{period_id}/pl-transfer")
    assert second.status_code == 400
    assert "已结转" in second.json()["detail"]

    # 反结转
    reverse = test_client.post(f"/api/accounting-periods/{period_id}/pl-transfer/reverse")
    assert reverse.status_code == 200
    assert reverse.json()["deleted_lines"] > 0

    # 反结转后可再次结转
    third = test_client.post(f"/api/accounting-periods/{period_id}/pl-transfer")
    assert third.status_code == 200


def test_pl_transfer_unknown_period_returns_404(client):
    test_client, _ = client
    resp = test_client.post("/api/accounting-periods/9999/pl-transfer")
    assert resp.status_code == 404
