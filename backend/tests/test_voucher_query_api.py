"""凭证聚合查询 API 测试。"""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import AccountingEntry, AccountingPeriod, Organization
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


def _register(client: TestClient, username: str, phone: str) -> dict:
    resp = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "testpass123",
            "phone": phone,
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_vouchers(db_factory, ledger_id: int, org_id: int) -> None:
    db = db_factory()
    try:
        db.add(
            AccountingPeriod(
                organization_id=org_id,
                ledger_id=ledger_id,
                period_code="2026-02",
                start_date=date(2026, 2, 1),
                end_date=date(2026, 2, 28),
                status="open",
            )
        )
        entries = [
            AccountingEntry(
                organization_id=org_id,
                import_job_id=1,
                ledger_id=ledger_id,
                voucher_no="记-010",
                voucher_date=date(2026, 2, 3),
                summary="报销差旅费",
                account_code="6601",
                account_name="销售费用",
                debit_amount=800,
                credit_amount=0,
                normalized_text="记-010",
                entry_line_no=1,
            ),
            AccountingEntry(
                organization_id=org_id,
                import_job_id=1,
                ledger_id=ledger_id,
                voucher_no="记-010",
                voucher_date=date(2026, 2, 3),
                summary="报销差旅费",
                account_code="1002",
                account_name="银行存款",
                debit_amount=0,
                credit_amount=800,
                normalized_text="记-010",
                entry_line_no=2,
            ),
            AccountingEntry(
                organization_id=org_id,
                import_job_id=1,
                ledger_id=ledger_id,
                voucher_no="收-020",
                voucher_date=date(2026, 2, 8),
                summary="收服务费",
                account_code="1002",
                account_name="银行存款",
                debit_amount=5000,
                credit_amount=0,
                normalized_text="收-020",
                entry_line_no=1,
            ),
            AccountingEntry(
                organization_id=org_id,
                import_job_id=1,
                ledger_id=ledger_id,
                voucher_no="收-020",
                voucher_date=date(2026, 2, 8),
                summary="收服务费",
                account_code="6001",
                account_name="主营业务收入",
                debit_amount=0,
                credit_amount=5000,
                normalized_text="收-020",
                entry_line_no=2,
            ),
        ]
        db.add_all(entries)
        db.commit()
    finally:
        db.close()


def test_voucher_query_line_mode_returns_cards(client):
    test_client, db_factory = client
    headers = _register(test_client, "voucher_query", "13800139200")
    team = test_client.post("/api/teams", json={"name": "凭证查询团队", "type": "firm"}, headers=headers).json()
    ledger = test_client.post(
        "/api/ledgers",
        json={"team_id": team["id"], "name": "凭证查询账簿"},
        headers=headers,
    ).json()

    db = db_factory()
    org = Organization(name="凭证企业", fiscal_year=2026)
    db.add(org)
    db.flush()
    org_id = org.id
    db.close()
    _seed_vouchers(db_factory, ledger["id"], org_id)

    by_account = test_client.get(
        f"/api/entries/vouchers?ledger_id={ledger['id']}&filter_mode=line&account_code=6601",
        headers=headers,
    )
    assert by_account.status_code == 200
    body = by_account.json()
    assert body["total"] == 1
    card = body["items"][0]
    assert card["voucher_no"] == "记-010"
    assert card["line_count"] == 2
    assert card["debit_total"] == 800

    by_month = test_client.get(
        f"/api/entries/vouchers?ledger_id={ledger['id']}&month=2026-02",
        headers=headers,
    )
    assert by_month.status_code == 200
    assert by_month.json()["total"] == 2


def test_voucher_query_voucher_mode_filters_totals(client):
    test_client, db_factory = client
    headers = _register(test_client, "voucher_total", "13800139201")
    team = test_client.post("/api/teams", json={"name": "合计团队", "type": "firm"}, headers=headers).json()
    ledger = test_client.post(
        "/api/ledgers",
        json={"team_id": team["id"], "name": "合计账簿"},
        headers=headers,
    ).json()

    db = db_factory()
    org = Organization(name="合计企业", fiscal_year=2026)
    db.add(org)
    db.flush()
    org_id = org.id
    db.close()
    _seed_vouchers(db_factory, ledger["id"], org_id)

    resp = test_client.get(
        f"/api/entries/vouchers?ledger_id={ledger['id']}&filter_mode=voucher&total_min=1000",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["voucher_no"] == "收-020"
    assert body["items"][0]["credit_total"] == 5000
