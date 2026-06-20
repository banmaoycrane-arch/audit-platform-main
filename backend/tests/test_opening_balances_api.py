from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import AccountingPeriod, Organization
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
    db = TestingSessionLocal()
    try:
        org = Organization(name="期初测试", fiscal_year=2026)
        db.add(org)
        db.flush()
        period = AccountingPeriod(
            organization_id=org.id,
            period_code="2026-01",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )
        db.add(period)
        db.commit()
        return org.id, period.id
    finally:
        db.close()


def test_upsert_and_list(client):
    test_client, TestingSessionLocal = client
    org_id, period_id = _seed(TestingSessionLocal)

    resp = test_client.post(
        "/api/opening-balances",
        json={
            "organization_id": org_id,
            "period_id": period_id,
            "account_code": "1002",
            "debit_balance": 1000,
            "credit_balance": 0,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["account_code"] == "1002"
    assert body["debit_balance"] == 1000

    listing = test_client.get(
        "/api/opening-balances",
        params={"organization_id": org_id, "period_id": period_id},
    ).json()
    assert len(listing) == 1


def test_repeat_upsert_does_not_duplicate(client):
    test_client, TestingSessionLocal = client
    org_id, period_id = _seed(TestingSessionLocal)

    payload = {
        "organization_id": org_id,
        "period_id": period_id,
        "account_code": "1002",
        "debit_balance": 1000,
    }
    test_client.post("/api/opening-balances", json=payload)
    payload["debit_balance"] = 2000
    second = test_client.post("/api/opening-balances", json=payload).json()
    assert second["debit_balance"] == 2000

    listing = test_client.get(
        "/api/opening-balances",
        params={"organization_id": org_id, "period_id": period_id},
    ).json()
    assert len(listing) == 1
    assert listing[0]["debit_balance"] == 2000


def test_bulk_upsert_and_trial_balance(client):
    test_client, TestingSessionLocal = client
    org_id, period_id = _seed(TestingSessionLocal)

    bulk = test_client.post(
        "/api/opening-balances/bulk",
        json={
            "organization_id": org_id,
            "period_id": period_id,
            "items": [
                {"account_code": "1002", "debit_balance": 1000},
                {"account_code": "2202", "credit_balance": 600},
                {"account_code": "4001", "credit_balance": 400},
            ],
        },
    )
    assert bulk.status_code == 200
    assert len(bulk.json()) == 3

    tb = test_client.get(
        "/api/opening-balances/trial-balance",
        params={"organization_id": org_id, "period_id": period_id},
    ).json()
    assert tb["debit_total"] == 1000
    assert tb["credit_total"] == 1000
    assert tb["is_balanced"] is True

    # 不平衡场景
    test_client.post(
        "/api/opening-balances",
        json={
            "organization_id": org_id,
            "period_id": period_id,
            "account_code": "4001",
            "credit_balance": 500,
        },
    )
    tb2 = test_client.get(
        "/api/opening-balances/trial-balance",
        params={"organization_id": org_id, "period_id": period_id},
    ).json()
    assert tb2["is_balanced"] is False


def test_delete_opening_balance(client):
    test_client, TestingSessionLocal = client
    org_id, period_id = _seed(TestingSessionLocal)

    created = test_client.post(
        "/api/opening-balances",
        json={
            "organization_id": org_id,
            "period_id": period_id,
            "account_code": "1002",
            "debit_balance": 1000,
        },
    ).json()

    resp = test_client.delete(f"/api/opening-balances/{created['id']}")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": created["id"]}

    listing = test_client.get(
        "/api/opening-balances",
        params={"organization_id": org_id, "period_id": period_id},
    ).json()
    assert listing == []


def test_delete_unknown_returns_404(client):
    test_client, _ = client
    resp = test_client.delete("/api/opening-balances/9999")
    assert resp.status_code == 404
