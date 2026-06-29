"""序时簿（按时间顺序分录）查询 API 测试。"""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import AccountingEntry, AccountingPeriod, Organization
from app.db.session import Base, get_db
from app.main import app
from app.models.ledger import Ledger
from app.models.user_ledger_auth import UserLedgerAuth


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


def _register(client: TestClient, username: str, phone: str) -> tuple[dict, int]:
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
    assert resp.status_code == 200
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    return headers, user_id


def _seed_entries(db_factory, ledger_id: int, org_id: int, job_id: int = 1) -> None:
    db = db_factory()
    try:
        period = AccountingPeriod(
            organization_id=org_id,
            ledger_id=ledger_id,
            period_code="2026-01",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            status="open",
        )
        db.add(period)
        db.flush()
        entries = [
            AccountingEntry(
                organization_id=org_id,
                import_job_id=job_id,
                ledger_id=ledger_id,
                voucher_no="记-001",
                voucher_date=date(2026, 1, 5),
                summary="支付办公费",
                account_code="6602",
                account_name="管理费用",
                debit_amount=500,
                credit_amount=0,
                normalized_text="记-001 管理费用",
                entry_line_no=1,
            ),
            AccountingEntry(
                organization_id=org_id,
                import_job_id=job_id,
                ledger_id=ledger_id,
                voucher_no="记-001",
                voucher_date=date(2026, 1, 5),
                summary="支付办公费",
                account_code="1002",
                account_name="银行存款",
                debit_amount=0,
                credit_amount=500,
                normalized_text="记-001 银行存款",
                entry_line_no=2,
            ),
            AccountingEntry(
                organization_id=org_id,
                import_job_id=job_id,
                ledger_id=ledger_id,
                voucher_no="收-002",
                voucher_date=date(2026, 1, 10),
                summary="收到货款",
                account_code="1122",
                account_name="应收账款",
                debit_amount=0,
                credit_amount=12000,
                normalized_text="收-002 应收账款",
                entry_line_no=1,
            ),
            AccountingEntry(
                organization_id=org_id,
                import_job_id=job_id,
                ledger_id=ledger_id,
                voucher_no="收-002",
                voucher_date=date(2026, 1, 10),
                summary="收到货款",
                account_code="1002",
                account_name="银行存款",
                debit_amount=12000,
                credit_amount=0,
                normalized_text="收-002 银行存款",
                entry_line_no=2,
            ),
        ]
        db.add_all(entries)
        db.commit()
        return period.id
    finally:
        db.close()


def test_chronological_entries_filter_by_account_and_voucher_word(client):
    test_client, db_factory = client
    headers, user_id = _register(test_client, "daybook_user", "13800139100")

    team = test_client.post(
        "/api/teams", json={"name": "序时簿团队", "type": "firm"}, headers=headers
    ).json()
    ledger = test_client.post(
        "/api/ledgers",
        json={"team_id": team["id"], "name": "序时簿账簿"},
        headers=headers,
    ).json()
    ledger_id = ledger["id"]

    db = db_factory()
    org = Organization(name="测试企业", fiscal_year=2026)
    db.add(org)
    db.flush()
    org_id = org.id
    db.close()

    period_id = _seed_entries(db_factory, ledger_id, org_id)

    by_code = test_client.get(
        f"/api/entries/chronological?ledger_id={ledger_id}&account_code=6602",
        headers=headers,
    )
    assert by_code.status_code == 200
    body = by_code.json()
    assert body["total"] == 1
    assert body["items"][0]["account_code"] == "6602"

    by_word = test_client.get(
        f"/api/entries/chronological?ledger_id={ledger_id}&voucher_word=收",
        headers=headers,
    )
    assert by_word.status_code == 200
    assert by_word.json()["total"] == 2

    by_summary = test_client.get(
        f"/api/entries/chronological?ledger_id={ledger_id}&summary=办公",
        headers=headers,
    )
    assert by_summary.status_code == 200
    assert by_summary.json()["total"] == 2

    by_amount = test_client.get(
        f"/api/entries/chronological?ledger_id={ledger_id}&amount_min=10000",
        headers=headers,
    )
    assert by_amount.status_code == 200
    assert by_amount.json()["total"] == 2

    by_period = test_client.get(
        f"/api/entries/chronological?ledger_id={ledger_id}&period_id={period_id}&date_from=2026-01-01&date_to=2026-01-31",
        headers=headers,
    )
    assert by_period.status_code == 200
    assert by_period.json()["total"] == 4

    ordered = test_client.get(
        f"/api/entries/chronological?ledger_id={ledger_id}&limit=10",
        headers=headers,
    ).json()["items"]
    assert ordered[0]["voucher_date"] <= ordered[-1]["voucher_date"]


def test_chronological_entries_requires_ledger_access(client):
    test_client, _ = client
    headers_a, _ = _register(test_client, "daybook_a", "13800139101")
    headers_b, _ = _register(test_client, "daybook_b", "13800139102")

    team = test_client.post(
        "/api/teams", json={"name": "隔离团队", "type": "firm"}, headers=headers_a
    ).json()
    ledger = test_client.post(
        "/api/ledgers",
        json={"team_id": team["id"], "name": "隔离账簿"},
        headers=headers_a,
    ).json()

    resp = test_client.get(
        f"/api/entries/chronological?ledger_id={ledger['id']}",
        headers=headers_b,
    )
    assert resp.status_code == 403
