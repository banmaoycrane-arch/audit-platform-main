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
            "phone": f"139{username[-7:]}",
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
    team = client.post("/api/teams", json={"name": "银行测试团队", "type": "company"}, headers=headers)
    assert team.status_code == 200
    ledger = client.post(
        "/api/ledgers",
        json={"team_id": team.json()["id"], "name": "银行测试账簿"},
        headers=headers,
    )
    assert ledger.status_code == 200
    ledger_id = ledger.json()["id"]
    switch = client.post(f"/api/ledgers/{ledger_id}/switch", headers=headers)
    assert switch.status_code == 200
    return ledger_id


def test_bank_account_and_transaction_flow(client):
    headers, _ = _auth_headers(client, "bank_user1")
    ledger_id = _create_ledger(client, headers)
    ledger_headers = {**headers, "X-Ledger-Id": str(ledger_id)}

    create_account = client.post(
        "/api/bank/accounts",
        json={
            "bank_name": "工商银行",
            "account_no": "62220200000001",
            "account_name": "测试公司",
            "opening_balance": 10000,
        },
        headers=ledger_headers,
    )
    assert create_account.status_code == 201
    account = create_account.json()
    assert account["current_balance"] == 10000

    create_txn = client.post(
        "/api/bank/transactions",
        json={
            "bank_account_id": account["id"],
            "transaction_date": "2026-06-15",
            "direction": "out",
            "amount": 1500,
            "summary": "支付供应商货款",
        },
        headers=ledger_headers,
    )
    assert create_txn.status_code == 201

    summary = client.get("/api/bank/summary", headers=ledger_headers)
    assert summary.status_code == 200
    assert summary.json()["account_count"] == 1
    assert summary.json()["unreconciled_count"] == 1


def test_auto_reconcile_matches_bank_and_ledger_entries(client):
    headers, _ = _auth_headers(client, "bank_user2")
    ledger_id = _create_ledger(client, headers)
    ledger_headers = {**headers, "X-Ledger-Id": str(ledger_id)}

    account = client.post(
        "/api/bank/accounts",
        json={
            "bank_name": "建设银行",
            "account_no": "62270000000002",
            "account_name": "测试公司",
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

    with next(app.dependency_overrides[get_db]()) as db:
        org = Organization(name="银行对账企业")
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
                voucher_no="记-001",
                voucher_date=date(2026, 6, 11),
                summary="客户回款",
                account_code="1002",
                account_name="银行存款",
                debit_amount=5000,
                credit_amount=0,
            )
        )
        db.commit()

    reconcile = client.post("/api/bank/reconcile/auto", headers=ledger_headers)
    assert reconcile.status_code == 200
    body = reconcile.json()
    assert body["matched_count"] == 1
    assert len(body["unmatched_transactions"]) == 0

    summary = client.get("/api/bank/summary", headers=ledger_headers)
    assert summary.json()["unreconciled_count"] == 0
