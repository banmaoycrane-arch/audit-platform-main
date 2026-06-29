"""Phase B2：往来函证控制表 API 测试。"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Contract, Counterparty, Invoice, Organization
from app.db.session import Base, get_db
from app.main import app
from app.models.ledger import Ledger
from app.models.team import Team


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
            test_client._SessionLocal = TestingSessionLocal  # type: ignore[attr-defined]
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _seed_receivable_and_payable(ledger_id: int) -> tuple[int, int]:
    with next(app.dependency_overrides[get_db]()) as db:
        org = Organization(name="函证测试组织")
        db.add(org)
        db.flush()

        receivable_cp = Counterparty(name="客户甲", role="customer")
        payable_cp = Counterparty(name="供应商乙", role="supplier")
        db.add(receivable_cp)
        db.add(payable_cp)
        db.flush()

        sales_contract = Contract(
            organization_id=org.id,
            ledger_id=ledger_id,
            contract_type="sales",
            contract_name="销售合同",
            execution_status="completed",
            counterparty_id=receivable_cp.id,
        )
        purchase_contract = Contract(
            organization_id=org.id,
            ledger_id=ledger_id,
            contract_type="purchase",
            contract_name="采购合同",
            execution_status="completed",
            counterparty_id=payable_cp.id,
        )
        db.add(sales_contract)
        db.add(purchase_contract)
        db.flush()

        db.add(
            Invoice(
                organization_id=org.id,
                ledger_id=ledger_id,
                invoice_type="增值税专用发票",
                buyer_name="客户甲",
                seller_name="本公司",
                total_amount=50000,
                related_contract_id=sales_contract.id,
                counterparty_id=receivable_cp.id,
            )
        )
        db.add(
            Invoice(
                organization_id=org.id,
                ledger_id=ledger_id,
                invoice_type="增值税专用发票",
                buyer_name="本公司",
                seller_name="供应商乙",
                total_amount=30000,
                related_contract_id=purchase_contract.id,
                counterparty_id=payable_cp.id,
            )
        )
        db.commit()
        return receivable_cp.id, payable_cp.id


def _seed_ledger(client: TestClient) -> tuple[dict, int]:
    register = client.post(
        "/api/auth/register",
        json={
            "username": "confirm_user",
            "phone": "13700000001",
            "password": "testpass123",
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    assert register.status_code == 200
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}
    team = client.post("/api/teams", json={"name": "函证团队", "type": "company"}, headers=headers)
    ledger = client.post(
        "/api/ledgers",
        json={"team_id": team.json()["id"], "name": "函证账簿"},
        headers=headers,
    )
    ledger_id = ledger.json()["id"]
    client.post(f"/api/ledgers/{ledger_id}/switch", headers=headers)
    return {**headers, "X-Ledger-Id": str(ledger_id)}, ledger_id


def test_generate_confirmations_from_counterparty_balances(client):
    headers, ledger_id = _seed_ledger(client)
    receivable_cp_id, payable_cp_id = _seed_receivable_and_payable(ledger_id)

    generated = client.post("/api/confirmations/generate", json={}, headers=headers)
    assert generated.status_code == 201
    rows = generated.json()
    assert len(rows) == 2

    balance_types = {row["balance_type"] for row in rows}
    assert balance_types == {"receivable", "payable"}

    receivable_row = next(row for row in rows if row["balance_type"] == "receivable")
    assert receivable_row["counterparty_id"] == receivable_cp_id
    assert receivable_row["book_balance"] == 50000
    assert receivable_row["confirmation_amount"] == 50000
    assert receivable_row["status"] == "draft"

    listing = client.get("/api/confirmations", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 2


def test_confirmation_reply_with_difference_marks_exception(client):
    headers, ledger_id = _seed_ledger(client)
    _seed_receivable_and_payable(ledger_id)

    generated = client.post("/api/confirmations/generate", json={}, headers=headers).json()
    receivable_row = next(row for row in generated if row["balance_type"] == "receivable")

    sent = client.patch(
        f"/api/confirmations/{receivable_row['id']}",
        json={"status": "sent"},
        headers=headers,
    )
    assert sent.status_code == 200
    assert sent.json()["status"] == "sent"
    assert sent.json()["sent_at"] is not None

    replied = client.post(
        f"/api/confirmations/{receivable_row['id']}/reply",
        json={"reply_amount": 48000},
        headers=headers,
    )
    assert replied.status_code == 200
    body = replied.json()
    assert body["reply_amount"] == 48000
    assert body["difference"] == -2000
    assert body["status"] == "exception"
    assert body["replied_at"] is not None


def test_confirmation_reply_matched_sets_replied_status(client):
    headers, ledger_id = _seed_ledger(client)
    _seed_receivable_and_payable(ledger_id)

    generated = client.post(
        "/api/confirmations/generate",
        json={"balance_types": ["payable"]},
        headers=headers,
    ).json()
    payable_row = generated[0]

    replied = client.post(
        f"/api/confirmations/{payable_row['id']}/reply",
        json={"reply_amount": 30000},
        headers=headers,
    )
    assert replied.status_code == 200
    body = replied.json()
    assert body["difference"] == 0
    assert body["status"] == "replied"


def test_generate_updates_existing_active_confirmation(client):
    headers, ledger_id = _seed_ledger(client)
    _seed_receivable_and_payable(ledger_id)

    first = client.post("/api/confirmations/generate", json={}, headers=headers).json()
    assert len(first) == 2

    with next(app.dependency_overrides[get_db]()) as db:
        team = Team(name="更新团队")
        db.add(team)
        db.flush()
        ledger = db.get(Ledger, ledger_id)
        org = db.query(Organization).first()
        contract = (
            db.query(Contract)
            .filter(Contract.ledger_id == ledger_id, Contract.contract_type == "sales")
            .one()
        )
        db.add(
            Invoice(
                organization_id=org.id,
                ledger_id=ledger_id,
                invoice_type="增值税专用发票",
                buyer_name="客户甲",
                seller_name="本公司",
                total_amount=10000,
                invoice_date=date(2026, 6, 20),
                related_contract_id=contract.id,
                counterparty_id=contract.counterparty_id,
            )
        )
        db.commit()

    second = client.post("/api/confirmations/generate", json={}, headers=headers).json()
    assert len(second) == 2
    receivable_row = next(row for row in second if row["balance_type"] == "receivable")
    assert receivable_row["book_balance"] == 60000
    assert receivable_row["confirmation_amount"] == 60000

    listing = client.get("/api/confirmations", headers=headers).json()
    assert len(listing) == 2
