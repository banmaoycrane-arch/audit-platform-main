"""AI 路径功能模块台账登记 API 测试。"""

import io
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes_imports import _import_reports
from app.db.models import BankStatement, Contract, ImportJob, Invoice
from app.db.session import Base, get_db
from app.main import app
from app.services.ledger_service import ledger_service


from tests.conftest import register_auth_headers


@pytest.fixture
def client(monkeypatch, tmp_path):
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

    monkeypatch.setattr("app.storage.local_storage.get_settings", lambda: SimpleNamespace(upload_dir=str(tmp_path)))
    monkeypatch.setattr("app.services.audit_day_book_service.safe_vector_store", lambda: None)
    monkeypatch.setattr("app.services.import_service.safe_vector_store", lambda: None)
    monkeypatch.setattr("app.services.register_ingestion_service.classify_document", lambda path, file_name="": __import__(
        "app.services.source_document_service", fromlist=["SourceDocumentResult"]
    ).SourceDocumentResult(
        document_type="invoice",
        confidence=0.9,
        data={
            "invoice_number": "INV-2026-001",
            "invoice_date": "2026-03-01",
            "buyer_name": "测试公司",
            "seller_name": "供应商A",
            "total_amount": 1200.0,
            "tax_amount": 130.0,
        },
        raw_text="发票号码 INV-2026-001",
        file_name=file_name or "invoice.pdf",
    ))
    ledger_service.invoice_ledger.clear()
    ledger_service.module_ledgers.clear()
    _import_reports.clear()
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            test_client._auth_headers = register_auth_headers(test_client)
            yield test_client, TestingSessionLocal
    finally:
        app.dependency_overrides.clear()
        _import_reports.clear()
        Base.metadata.drop_all(bind=engine)


def test_ai_upload_registers_tax_invoice_module(client):
    test_client, TestingSessionLocal = client
    create_response = test_client.post(
        "/api/import-jobs",
        json={"organization_name": "台账登记测试", "source_type": "ai_generated"},
        headers=test_client._auth_headers,
    )
    job_id = create_response.json()["id"]

    upload_response = test_client.post(
        f"/api/import-jobs/{job_id}/files",
        data={"document_type_hints": "invoice"},
        files={"file": ("invoice.pdf", io.BytesIO(b"fake pdf"), "application/pdf")},
    )
    assert upload_response.status_code == 200

    process_response = test_client.post(f"/api/import-jobs/{job_id}/process/sync")
    assert process_response.status_code == 200
    report = process_response.json()["report"]
    assert report["output_path"] == "register_ledger"
    assert report["total_entries"] == 0
    assert report["register_summary"][0]["module_registrations"][0]["module_key"] == "tax_invoice"

    db = TestingSessionLocal()
    try:
        invoices = db.query(Invoice).all()
        assert len(invoices) == 1
        assert invoices[0].source_file_id is not None
        assert "tax_invoice" in ledger_service.module_ledgers
    finally:
        db.close()


def test_ai_upload_contract_registers_multiple_modules(client, monkeypatch):
    from app.services.source_document_service import SourceDocumentResult

    monkeypatch.setattr(
        "app.services.register_ingestion_service.classify_document",
        lambda path, file_name="": SourceDocumentResult(
            document_type="contract",
            confidence=0.9,
            data={
                "contract_number": "CG-2026-001",
                "party_a": "本公司",
                "party_b": "供应商A",
                "amount": 50000,
                "sign_date": "2026-03-01",
            },
            raw_text="采购合同 甲方：本公司 乙方：供应商A",
            file_name=file_name or "采购合同.pdf",
        ),
    )

    test_client, TestingSessionLocal = client
    create_response = test_client.post(
        "/api/import-jobs",
        json={"organization_name": "采购合同台账测试", "source_type": "ai_generated"},
        headers=test_client._auth_headers,
    )
    job_id = create_response.json()["id"]

    test_client.post(
        f"/api/import-jobs/{job_id}/files",
        files={"file": ("采购合同.pdf", io.BytesIO(b"contract"), "application/pdf")},
    )
    process_response = test_client.post(f"/api/import-jobs/{job_id}/process/sync")
    assert process_response.status_code == 200

    module_regs = process_response.json()["report"]["register_summary"][0]["module_registrations"]
    module_keys = {item["module_key"] for item in module_regs}
    assert "contract_register" in module_keys
    assert "purchase" in module_keys
    assert "counterparty_ledger" not in module_keys

    db = TestingSessionLocal()
    try:
        contracts = db.query(Contract).all()
        assert len(contracts) == 1
        assert "contract_register" in ledger_service.module_ledgers
        assert "purchase" in ledger_service.module_ledgers
    finally:
        db.close()
