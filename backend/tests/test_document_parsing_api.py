import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import BankStatement, Contract, ContractParty, InventoryDocument, Invoice, Organization
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


def seed_organization(TestingSessionLocal):
    db = TestingSessionLocal()
    try:
        organization = Organization(name="原始文件解析测试企业", fiscal_year=2026)
        db.add(organization)
        db.commit()
        return organization.id
    finally:
        db.close()


def test_parse_contract_api_creates_contract(client):
    test_client, TestingSessionLocal = client
    organization_id = seed_organization(TestingSessionLocal)

    response = test_client.post(
        "/api/parse/contract",
        json={
            "organization_id": organization_id,
            "contract_no": "HT-2026-001",
            "contract_type": "purchase",
            "contract_name": "采购合同",
            "sign_date": "2026-01-01",
            "contract_amount": 100000,
            "parties": [
                {"party_role": "party_a", "party_name": "本公司"},
                {"party_role": "party_b", "party_name": "供应商A"},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_type"] == "contract"
    assert payload["data"]["contract_no"] == "HT-2026-001"

    db = TestingSessionLocal()
    try:
        assert db.query(Contract).count() == 1
    finally:
        db.close()


def test_parse_contract_extracts_parties_from_text(client):
    test_client, TestingSessionLocal = client
    organization_id = seed_organization(TestingSessionLocal)

    response = test_client.post(
        "/api/parse/contract",
        json={
            "organization_id": organization_id,
            "contract_no": "HT-2026-002",
            "contract_name": "三方担保采购合同",
            "extracted_text": "甲方：北京甲方科技有限公司\n乙方: 上海乙方商贸有限公司\n丙方（担保方）：深圳丙方担保有限公司。",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    parties = payload["data"]["parties"]
    assert len(parties) >= 3
    assert {party["party_role"] for party in parties} >= {"party_a", "party_b", "party_c"}

    db = TestingSessionLocal()
    try:
        assert db.query(ContractParty).count() == 3
    finally:
        db.close()


def test_parse_contract_merges_explicit_and_text_parties(client):
    test_client, TestingSessionLocal = client
    organization_id = seed_organization(TestingSessionLocal)

    response = test_client.post(
        "/api/parse/contract",
        json={
            "organization_id": organization_id,
            "contract_no": "HT-2026-003",
            "contract_name": "带担保方采购合同",
            "parties": [
                {"party_role": "party_a", "party_name": "北京甲方科技有限公司"},
                {"party_role": "party_b", "party_name": "上海乙方商贸有限公司"},
            ],
            "extracted_text": "甲方：北京甲方科技有限公司；乙方：上海乙方商贸有限公司；丙方（担保方）：深圳丙方担保有限公司。",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    parties = payload["data"]["parties"]
    assert len(parties) == 3
    assert any(party["party_role"] == "party_c" and party["party_name"] == "深圳丙方担保有限公司" for party in parties)

    db = TestingSessionLocal()
    try:
        assert db.query(ContractParty).count() == 3
    finally:
        db.close()


def test_parse_invoice_api_creates_invoice(client):
    test_client, TestingSessionLocal = client
    organization_id = seed_organization(TestingSessionLocal)

    response = test_client.post(
        "/api/parse/invoice",
        json={
            "organization_id": organization_id,
            "invoice_no": "1234567890",
            "invoice_date": "2026-01-05",
            "buyer_name": "本公司",
            "seller_name": "供应商A",
            "total_amount": 1130,
            "tax_amount": 130,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_type"] == "invoice"
    assert payload["data"]["invoice_no"] == "1234567890"

    db = TestingSessionLocal()
    try:
        assert db.query(Invoice).count() == 1
    finally:
        db.close()


def test_parse_bank_statement_api_creates_statement(client):
    test_client, TestingSessionLocal = client
    organization_id = seed_organization(TestingSessionLocal)

    response = test_client.post(
        "/api/parse/bank-statement",
        json={
            "organization_id": organization_id,
            "transaction_no": "BANK-001",
            "transaction_date": "2026-01-06",
            "transaction_type": "expense",
            "counterparty_name": "供应商A",
            "amount": 1130,
            "summary": "支付货款",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_type"] == "bank_statement"
    assert payload["data"]["transaction_no"] == "BANK-001"

    db = TestingSessionLocal()
    try:
        assert db.query(BankStatement).count() == 1
    finally:
        db.close()


def test_parse_inventory_document_api_creates_inventory_document(client):
    test_client, TestingSessionLocal = client
    organization_id = seed_organization(TestingSessionLocal)

    response = test_client.post(
        "/api/parse/inventory-document",
        json={
            "organization_id": organization_id,
            "document_no": "RK-001",
            "document_type": "inventory_in",
            "document_date": "2026-01-04",
            "warehouse_name": "一号仓",
            "counterparty_name": "供应商A",
            "total_quantity": 10,
            "total_amount": 1000,
            "items": [{"item_no": 1, "goods_name": "原材料A", "quantity": 10, "amount": 1000}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_type"] == "inventory_document"
    assert payload["data"]["document_no"] == "RK-001"

    db = TestingSessionLocal()
    try:
        assert db.query(InventoryDocument).count() == 1
    finally:
        db.close()


def test_parse_document_unknown_organization_returns_404(client):
    test_client, _ = client

    response = test_client.post(
        "/api/parse/invoice",
        json={"organization_id": 999, "invoice_no": "1234567890"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "组织不存在"
