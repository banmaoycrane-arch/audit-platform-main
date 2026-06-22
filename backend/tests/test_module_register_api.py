"""Phase A：模块台账持久化与查询 API 测试。"""

import io
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Contract, ImportJob, Organization, SourceFile
from app.db.session import Base, get_db
from app.main import app
from app.models.ledger import Ledger
from app.models.team import Team
from app.services.ledger_service import ledger_service
from app.services.source_document_service import SourceDocumentResult


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
        ledger_service.module_ledgers.clear()
        Base.metadata.drop_all(bind=engine)


def _seed_ledger(db) -> int:
    team = Team(name="PhaseA团队")
    db.add(team)
    db.flush()
    ledger = Ledger(name="PhaseA账套", team_id=team.id)
    db.add(ledger)
    db.commit()
    return ledger.id


def test_module_register_summary_and_contract_query(client):
    test_client = client
    TestingSessionLocal = client._SessionLocal  # type: ignore[attr-defined]
    db = TestingSessionLocal()
    try:
        ledger_id = _seed_ledger(db)
        org = Organization(name="PhaseA组织")
        db.add(org)
        db.flush()
        contract = Contract(
            organization_id=org.id,
            ledger_id=ledger_id,
            contract_no="HT-001",
            contract_type="purchase",
            contract_name="采购合同A",
            execution_status="pending",
        )
        db.add(contract)
        db.commit()
    finally:
        db.close()

    summary = test_client.get(f"/api/module-registers/summary?ledger_id={ledger_id}")
    assert summary.status_code == 200
    body = summary.json()
    assert body["modules"]["contract_register"]["count"] == 1

    listing = test_client.get(f"/api/module-registers/contract_register?ledger_id={ledger_id}")
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert len(items) == 1
    assert items[0]["contract_no"] == "HT-001"
    assert items[0]["execution_status"] == "pending"


@patch("app.services.register_ingestion_service.classify_document")
def test_ai_import_persists_ledger_id_on_contract(mock_classify, client):
    mock_classify.return_value = SourceDocumentResult(
        document_type="contract",
        confidence=0.95,
        data={
            "contract_number": "CG-2026-01",
            "party_a": "本公司",
            "party_b": "供应商A",
            "amount": 120000,
            "sign_date": "2026-03-01",
        },
        raw_text="采购合同 待执行",
        file_name="采购合同.pdf",
    )

    test_client = client
    TestingSessionLocal = client._SessionLocal  # type: ignore[attr-defined]
    db = TestingSessionLocal()
    try:
        ledger_id = _seed_ledger(db)
    finally:
        db.close()

    job = test_client.post(
        "/api/import-jobs",
        json={"organization_name": "PhaseA导入", "source_type": "ai_generated", "ledger_id": ledger_id},
    ).json()

    test_client.post(
        f"/api/import-jobs/{job['id']}/files",
        files={"file": ("采购合同.pdf", io.BytesIO(b"contract"), "application/pdf")},
    )
    process = test_client.post(f"/api/import-jobs/{job['id']}/process/sync")
    assert process.status_code == 200

    db = TestingSessionLocal()
    try:
        contract = db.query(Contract).one()
        assert contract.ledger_id == ledger_id
        assert contract.execution_status == "pending"
    finally:
        db.close()

    listing = test_client.get(f"/api/module-registers/purchase?ledger_id={ledger_id}")
    assert listing.status_code == 200
    assert listing.json()["count"] >= 1


def test_counterparty_balance_view_from_invoices(client):
    test_client = client
    TestingSessionLocal = client._SessionLocal  # type: ignore[attr-defined]
    db = TestingSessionLocal()
    try:
        from app.db.models import Invoice

        ledger_id = _seed_ledger(db)
        org = Organization(name="往来测试组织")
        db.add(org)
        db.flush()
        contract = Contract(
            organization_id=org.id,
            ledger_id=ledger_id,
            contract_type="sales",
            contract_name="销售合同",
            execution_status="completed",
        )
        db.add(contract)
        db.flush()
        db.add(
            Invoice(
                organization_id=org.id,
                ledger_id=ledger_id,
                invoice_type="增值税专用发票",
                buyer_name="客户甲",
                seller_name="本公司",
                total_amount=50000,
                related_contract_id=contract.id,
            )
        )
        db.commit()
    finally:
        db.close()

    response = test_client.get(f"/api/module-registers/counterparty_ledger?ledger_id={ledger_id}")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["balance_type"] == "receivable"
    assert items[0]["total_amount"] == 50000.0
