"""Phase D：审计工作流编排 API 测试。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Contract, Counterparty, InventoryDocument, Invoice, Organization, SourceFile
from app.db.session import Base, get_db
from app.main import app
from app.models.project import Project
from app.models.project_ledger import ProjectLedger
from app.models.team import Team
from app.services.draft_semantic_decomposition_service import decompose_draft
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
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _auth_headers(client: TestClient, username: str) -> dict:
    register = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "phone": f"134{username[-7:]}",
            "password": "testpass123",
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    assert register.status_code == 200
    return {"Authorization": f"Bearer {register.json()['access_token']}"}


def _create_ledger_with_project(client: TestClient, headers: dict) -> tuple[dict, int, int]:
    team = client.post("/api/teams", json={"name": "工作流团队", "type": "company"}, headers=headers)
    project = client.post(
        "/api/projects",
        json={"team_id": team.json()["id"], "name": "工作流项目", "project_type": "audit"},
        headers=headers,
    )
    ledger = client.post(
        "/api/ledgers",
        json={"team_id": team.json()["id"], "name": "工作流账套"},
        headers=headers,
    )
    ledger_id = ledger.json()["id"]
    project_id = project.json()["id"]
    client.post(f"/api/ledgers/{ledger_id}/switch", headers=headers)
    client.post(
        f"/api/projects/{project_id}/ledgers",
        json={"ledger_id": ledger_id},
        headers=headers,
    )
    return {**headers, "X-Ledger-Id": str(ledger_id)}, ledger_id, project_id


def test_workflow_config_and_procedure_advance(client):
    headers = _auth_headers(client, "wf_user1")
    ledger_headers, ledger_id, project_id = _create_ledger_with_project(client, headers)

    config = client.put(
        f"/api/audit/workflow/config?project_id={project_id}",
        json={
            "granularity": "fine",
            "enabled_procedures": ["counterparty_confirmation", "bank_reconciliation"],
            "auto_link_workpaper": True,
        },
        headers=ledger_headers,
    )
    assert config.status_code == 200
    assert config.json()["granularity"] == "fine"

    created = client.post(
        "/api/audit/workflow/runs/from-recommendations",
        json={
            "recommendations": [
                {
                    "procedure_key": "counterparty_confirmation",
                    "procedure_label": "往来函证",
                    "source_module_key": "counterparty_ledger",
                    "workpaper_index_hint": "B 往来款项",
                }
            ],
            "project_id": project_id,
        },
        headers=ledger_headers,
    )
    assert created.status_code == 200
    run = created.json()[0]
    assert run["status"] == "planned"

    advanced = client.post(
        f"/api/audit/workflow/runs/{run['id']}/advance",
        json={"action": "start"},
        headers=ledger_headers,
    )
    assert advanced.status_code == 200
    assert advanced.json()["status"] == "initiated"


def test_decomposition_recommends_audit_procedures():
    classification = SourceDocumentResult(
        document_type="bank_statement",
        confidence=0.9,
        data={"transactions": [{"amount": 100}]},
        raw_text="银行流水 对账单",
        file_name="bank.pdf",
    )
    decomposition = decompose_draft(classification)
    payload = decomposition.to_dict()
    assert payload.get("workpaper_index_hint")
    assert any(item["procedure_key"] == "bank_reconciliation" for item in payload["recommended_audit_procedures"])


def test_confirmation_syncs_workflow_run(client):
    headers = _auth_headers(client, "wf_user2")
    ledger_headers, ledger_id, project_id = _create_ledger_with_project(client, headers)

    with next(app.dependency_overrides[get_db]()) as db:
        org = Organization(name="工作流组织")
        db.add(org)
        db.flush()
        cp = Counterparty(name="客户A", role="customer")
        db.add(cp)
        db.flush()
        contract = Contract(
            organization_id=org.id,
            ledger_id=ledger_id,
            contract_type="sales",
            contract_name="销售合同",
            execution_status="completed",
            counterparty_id=cp.id,
        )
        db.add(contract)
        db.flush()
        db.add(
            Invoice(
                organization_id=org.id,
                ledger_id=ledger_id,
                invoice_type="增值税专用发票",
                buyer_name="客户A",
                seller_name="本公司",
                total_amount=10000,
                related_contract_id=contract.id,
                counterparty_id=cp.id,
            )
        )
        db.commit()

    confirmation = client.post("/api/confirmations/generate", json={}, headers=ledger_headers).json()[0]
    client.patch(
        f"/api/confirmations/{confirmation['id']}",
        json={"status": "sent"},
        headers=ledger_headers,
    )
    client.post(
        f"/api/confirmations/{confirmation['id']}/reply",
        json={"reply_amount": 10000},
        headers=ledger_headers,
    )

    runs = client.get("/api/audit/workflow/runs", headers=ledger_headers).json()
    assert len(runs) >= 1
    confirmation_run = next((item for item in runs if item["procedure_key"] == "counterparty_confirmation"), None)
    assert confirmation_run is not None
    assert confirmation_run["status"] in {"in_review", "concluded"}


def test_bank_reconciliation_syncs_workflow_run(client):
    headers = _auth_headers(client, "wf_user3")
    ledger_headers, ledger_id, _project_id = _create_ledger_with_project(client, headers)

    account = client.post(
        "/api/bank/accounts",
        json={
            "bank_name": "招商银行",
            "account_no": "62258888000002",
            "account_name": "工作流公司",
            "opening_balance": 5000,
        },
        headers=ledger_headers,
    ).json()

    draft = client.post(
        "/api/bank/reconciliations",
        json={
            "bank_account_id": account["id"],
            "period_end": "2026-06-30",
            "statement_balance": 5000,
        },
        headers=ledger_headers,
    )
    assert draft.status_code == 201
    body = draft.json()
    assert body["status"] == "draft"

    runs = client.get("/api/audit/workflow/runs", headers=ledger_headers).json()
    bank_run = next((item for item in runs if item["procedure_key"] == "bank_reconciliation"), None)
    assert bank_run is not None
    assert bank_run["status"] == "in_review"
    assert bank_run["related_entity_id"] == body["id"]


def test_purchase_match_syncs_workflow_run(client):
    headers = _auth_headers(client, "wf_user4")
    ledger_headers, ledger_id, _project_id = _create_ledger_with_project(client, headers)

    with next(app.dependency_overrides[get_db]()) as db:
        org = Organization(name="采购组织")
        db.add(org)
        db.flush()
        contract = Contract(
            organization_id=org.id,
            ledger_id=ledger_id,
            contract_type="purchase",
            contract_name="采购合同A",
            contract_amount=100000,
            execution_status="completed",
        )
        db.add(contract)
        db.flush()
        db.add(
            Invoice(
                organization_id=org.id,
                ledger_id=ledger_id,
                invoice_type="增值税专用发票",
                buyer_name="本公司",
                seller_name="供应商A",
                total_amount=100000,
                related_contract_id=contract.id,
            )
        )
        db.add(
            InventoryDocument(
                organization_id=org.id,
                ledger_id=ledger_id,
                document_no="RK-001",
                document_type="inventory_in",
                counterparty_name="供应商A",
                total_amount=100000,
                related_contract_id=contract.id,
            )
        )
        db.commit()
        contract_id = contract.id

    match = client.get(f"/api/audit/purchase-match?contract_id={contract_id}", headers=ledger_headers)
    assert match.status_code == 200
    assert match.json()[0]["match_status"] == "matched"

    runs = client.get("/api/audit/workflow/runs", headers=ledger_headers).json()
    purchase_run = next((item for item in runs if item["procedure_key"] == "purchase_three_way_match"), None)
    assert purchase_run is not None
    assert purchase_run["status"] == "concluded"
    assert purchase_run["related_entity_id"] == contract_id
