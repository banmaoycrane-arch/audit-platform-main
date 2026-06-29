"""Phase B3：采购三单匹配 API 测试。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Contract, InventoryDocument, Invoice, Organization
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


def _auth_headers(client: TestClient, username: str) -> dict:
    register = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "phone": f"136{username[-7:]}",
            "password": "testpass123",
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    assert register.status_code == 200
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}
    return headers


def _create_ledger(client: TestClient, headers: dict) -> tuple[dict, int]:
    team = client.post("/api/teams", json={"name": "三单匹配团队", "type": "company"}, headers=headers)
    ledger = client.post(
        "/api/ledgers",
        json={"team_id": team.json()["id"], "name": "三单匹配账簿"},
        headers=headers,
    )
    ledger_id = ledger.json()["id"]
    client.post(f"/api/ledgers/{ledger_id}/switch", headers=headers)
    return {**headers, "X-Ledger-Id": str(ledger_id)}, ledger_id


def _seed_purchase_contract(
    ledger_id: int,
    *,
    contract_amount: float = 100000,
    with_invoice: bool = True,
    with_inventory: bool = True,
    invoice_amount: float | None = None,
    inventory_amount: float | None = None,
) -> int:
    invoice_amount = invoice_amount if invoice_amount is not None else contract_amount
    inventory_amount = inventory_amount if inventory_amount is not None else contract_amount

    with next(app.dependency_overrides[get_db]()) as db:
        org = Organization(name="三单匹配组织")
        db.add(org)
        db.flush()
        contract = Contract(
            organization_id=org.id,
            ledger_id=ledger_id,
            contract_type="purchase",
            contract_no="CG-2026-001",
            contract_name="设备采购合同",
            contract_amount=contract_amount,
            execution_status="executing",
        )
        db.add(contract)
        db.flush()

        if with_invoice:
            db.add(
                Invoice(
                    organization_id=org.id,
                    ledger_id=ledger_id,
                    invoice_type="增值税专用发票",
                    buyer_name="本公司",
                    seller_name="供应商A",
                    total_amount=invoice_amount,
                    related_contract_id=contract.id,
                )
            )
        if with_inventory:
            db.add(
                InventoryDocument(
                    organization_id=org.id,
                    ledger_id=ledger_id,
                    document_no="RK-2026-001",
                    document_type="inventory_in",
                    counterparty_name="供应商A",
                    total_amount=inventory_amount,
                    related_contract_id=contract.id,
                )
            )
        db.commit()
        return contract.id


def test_three_way_match_complete(client):
    headers = _auth_headers(client, "match_user1")
    ledger_headers, ledger_id = _create_ledger(client, headers)
    contract_id = _seed_purchase_contract(ledger_id)

    response = client.get(f"/api/audit/purchase-match?contract_id={contract_id}", headers=ledger_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    result = body[0]
    assert result["match_status"] == "matched"
    assert len(result["exceptions"]) == 0
    assert all(check["passed"] for check in result["checks"])


def test_three_way_match_missing_invoice(client):
    headers = _auth_headers(client, "match_user2")
    ledger_headers, ledger_id = _create_ledger(client, headers)
    contract_id = _seed_purchase_contract(ledger_id, with_invoice=False)

    response = client.get(f"/api/audit/purchase-match?contract_id={contract_id}", headers=ledger_headers)
    result = response.json()[0]
    assert result["match_status"] == "incomplete"
    types = {item["exception_type"] for item in result["exceptions"]}
    assert "missing_invoice" in types


def test_three_way_match_amount_mismatch(client):
    headers = _auth_headers(client, "match_user3")
    ledger_headers, ledger_id = _create_ledger(client, headers)
    contract_id = _seed_purchase_contract(ledger_id, invoice_amount=90000)

    response = client.get(f"/api/audit/purchase-match?contract_id={contract_id}", headers=ledger_headers)
    result = response.json()[0]
    assert result["match_status"] == "exception"
    types = {item["exception_type"] for item in result["exceptions"]}
    assert "amount_mismatch" in types


def test_purchase_match_summary_lists_exceptions(client):
    headers = _auth_headers(client, "match_user4")
    ledger_headers, ledger_id = _create_ledger(client, headers)
    _seed_purchase_contract(ledger_id)
    _seed_purchase_contract(ledger_id, with_invoice=False, contract_amount=50000)

    summary = client.get("/api/audit/purchase-match/summary", headers=ledger_headers)
    assert summary.status_code == 200
    body = summary.json()
    assert body["contract_count"] == 2
    assert body["matched_count"] == 1
    assert body["incomplete_count"] == 1
    assert len(body["exception_items"]) >= 1
