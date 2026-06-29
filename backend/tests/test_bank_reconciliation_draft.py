"""Phase B1：银行调节表草稿 API 测试。"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import AccountingEntry, ImportJob, Organization
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
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _auth_headers(client: TestClient, username: str) -> tuple[dict, int]:
    register = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "phone": f"138{username[-7:]}",
            "password": "testpass123",
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    assert register.status_code == 200
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/auth/me", headers=headers)
    return headers, me.json()["id"]


def _create_ledger(client: TestClient, headers: dict) -> int:
    team = client.post("/api/teams", json={"name": "调节表团队", "type": "company"}, headers=headers)
    assert team.status_code == 200
    ledger = client.post(
        "/api/ledgers",
        json={"team_id": team.json()["id"], "name": "调节表账簿"},
        headers=headers,
    )
    assert ledger.status_code == 200
    ledger_id = ledger.json()["id"]
    switch = client.post(f"/api/ledgers/{ledger_id}/switch", headers=headers)
    assert switch.status_code == 200
    return ledger_id


def _seed_gl_entry(ledger_id: int, *, voucher_date: date, debit: float = 0, credit: float = 0, summary: str = "测试分录"):
    with next(app.dependency_overrides[get_db]()) as db:
        org = Organization(name="调节表企业")
        db.add(org)
        db.flush()
        job = ImportJob(organization_id=org.id, ledger_id=ledger_id)
        db.add(job)
        db.flush()
        db.add(
            AccountingEntry(
                organization_id=org.id,
                ledger_id=ledger_id,
                import_job_id=job.id,
                voucher_no="记-调节",
                voucher_date=voucher_date,
                summary=summary,
                account_code="1002",
                account_name="银行存款",
                debit_amount=debit,
                credit_amount=credit,
            )
        )
        db.commit()


def test_bank_reconciliation_draft_with_outstanding_items(client):
    headers, _ = _auth_headers(client, "recon_user1")
    ledger_id = _create_ledger(client, headers)
    ledger_headers = {**headers, "X-Ledger-Id": str(ledger_id)}

    account = client.post(
        "/api/bank/accounts",
        json={
            "bank_name": "招商银行",
            "account_no": "62258888000001",
            "account_name": "调节表公司",
            "opening_balance": 10000,
        },
        headers=ledger_headers,
    ).json()

    client.post(
        "/api/bank/transactions",
        json={
            "bank_account_id": account["id"],
            "transaction_date": "2026-06-20",
            "direction": "out",
            "amount": 2000,
            "summary": "银行已付、账上未记",
        },
        headers=ledger_headers,
    )

    _seed_gl_entry(ledger_id, voucher_date=date(2026, 6, 18), debit=3000, summary="企业已收、银行未收")

    draft = client.post(
        "/api/bank/reconciliations",
        json={
            "bank_account_id": account["id"],
            "period_end": "2026-06-30",
            "statement_balance": 8000,
        },
        headers=ledger_headers,
    )
    assert draft.status_code == 201
    body = draft.json()

    assert body["statement_balance"] == 8000
    assert body["book_balance"] == 3000
    assert body["adjusted_statement_balance"] == 11000
    assert body["adjusted_book_balance"] == 1000
    assert body["difference"] == 10000
    assert body["status"] == "draft"
    assert len(body["items"]) == 2
    item_types = {item["item_type"] for item in body["items"]}
    assert item_types == {"bank_debit_not_in_books", "outstanding_deposit"}

    listing = client.get("/api/bank/reconciliations", headers=ledger_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    detail = client.get(f"/api/bank/reconciliations/{body['id']}", headers=ledger_headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == body["id"]


def test_bank_reconciliation_draft_balanced_after_auto_match(client):
    headers, _ = _auth_headers(client, "recon_user2")
    ledger_id = _create_ledger(client, headers)
    ledger_headers = {**headers, "X-Ledger-Id": str(ledger_id)}

    account = client.post(
        "/api/bank/accounts",
        json={
            "bank_name": "中国银行",
            "account_no": "62170000000003",
            "account_name": "平衡测试公司",
        },
        headers=ledger_headers,
    ).json()

    client.post(
        "/api/bank/transactions",
        json={
            "bank_account_id": account["id"],
            "transaction_date": "2026-06-10",
            "direction": "in",
            "amount": 5000,
            "summary": "客户回款",
        },
        headers=ledger_headers,
    )

    _seed_gl_entry(ledger_id, voucher_date=date(2026, 6, 11), debit=5000, summary="客户回款")

    draft = client.post(
        "/api/bank/reconciliations",
        json={
            "bank_account_id": account["id"],
            "period_end": "2026-06-30",
        },
        headers=ledger_headers,
    )
    assert draft.status_code == 201
    body = draft.json()
    assert body["status"] == "balanced"
    assert body["difference"] == 0
    assert body["adjusted_statement_balance"] == body["adjusted_book_balance"]
    assert len(body["items"]) == 0
