from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import AccountingEntry, AuditFinding, AuditRisk, ImportJob, Organization, SourceFile
from app.models.ledger import Ledger
from app.db.session import Base, get_db
from app.main import app

client: TestClient


@pytest.fixture(autouse=True)
def _isolated_workbench_client(monkeypatch):
    global client
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr("app.db.session.SessionLocal", testing_session_local)
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            client = test_client
            yield
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def auth_headers(client: TestClient, username: str, phone: str) -> dict[str, str]:
    suffix = uuid4().hex[:8]
    phone_suffix = str(uuid4().int % 100).zfill(2)
    response = client.post(
        "/api/auth/register",
        json={
            "username": f"{username}_{suffix}",
            "phone": f"{phone}{phone_suffix}",
            "password": "password123",
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_ledger_headers(client: TestClient, username: str, phone: str) -> tuple[dict[str, str], int]:
    headers = auth_headers(client, username, phone)
    team = client.post("/api/teams", json={"name": f"团队_{username}", "type": "company"}, headers=headers)
    assert team.status_code == 200
    ledger = client.post(
        "/api/ledgers",
        json={"team_id": team.json()["id"], "name": f"账簿_{username}"},
        headers=headers,
    )
    assert ledger.status_code == 200
    ledger_id = ledger.json()["id"]
    switch = client.post(f"/api/ledgers/{ledger_id}/switch", headers=headers)
    assert switch.status_code == 200
    return {**headers, "X-Ledger-Id": str(ledger_id)}, ledger_id


def seed_ledger_workbench_data(ledger_id: int) -> tuple[int, int]:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        ledger = db.get(Ledger, ledger_id)
        assert ledger is not None
        org = Organization(name="Workbench Org")
        db.add(org)
        db.flush()
        job = ImportJob(
            organization_id=org.id,
            ledger_id=ledger_id,
            status="created",
            source_type="voucher_import",
        )
        db.add(job)
        db.flush()
        db.add(
            AuditFinding(
                job_id=job.id,
                ledger_id=ledger_id,
                finding_uuid=uuid4().hex,
                finding_type="internal_control",
                severity="medium",
                finding_title="银行户名未规范",
                finding_description="测试内控待办",
                status="pending",
            )
        )
        db.add(
            AuditRisk(
                organization_id=org.id,
                ledger_id=ledger_id,
                import_job_id=job.id,
                risk_type="vector_similarity",
                risk_level="high",
                title="异常相似分录",
                description="测试风险提醒",
                status="pending_review",
            )
        )
        source_file = SourceFile(
            organization_id=org.id,
            import_job_id=job.id,
            ledger_id=ledger_id,
            filename="invoice.pdf",
            file_type="invoice",
            storage_path="/tmp/invoice.pdf",
            text_extract_status="pending",
        )
        db.add(source_file)
        db.flush()
        db.add(
            AccountingEntry(
                organization_id=org.id,
                ledger_id=ledger_id,
                import_job_id=job.id,
                voucher_no="记-001",
                account_code="1001",
                account_name="库存现金",
                debit_amount=100,
                credit_amount=0,
                entry_line_no=1,
                source_file_id=source_file.id,
            )
        )
        db.commit()
        return job.id, source_file.id
    finally:
        db.close()


def test_workbench_items_requires_ledger_header():
    headers = auth_headers(client, "workbench_no_ledger", "13800139201")
    response = client.get("/api/workbench/items", headers=headers)
    assert response.status_code == 400


def test_workbench_items_merges_sources():
    headers, ledger_id = create_ledger_headers(client, "workbench_merge", "13800139202")
    job_id, _ = seed_ledger_workbench_data(ledger_id)
    response = client.get("/api/workbench/items", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["ledger_id"] == ledger_id
    assert data["summary"]["total"] >= 2
    sources = {item["source"] for item in data["items"]}
    assert "internal_control" in sources
    assert "risk" in sources
    assert any(item.get("job_id") == job_id for item in data["items"])


def test_entry_source_evidence_links_file():
    headers, ledger_id = create_ledger_headers(client, "entry_evidence", "13800139203")
    _, source_file_id = seed_ledger_workbench_data(ledger_id)
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        entry = db.query(AccountingEntry).filter(AccountingEntry.ledger_id == ledger_id).first()
        entry_id = entry.id
    finally:
        db.close()

    response = client.get(f"/api/entries/{entry_id}/source-evidence", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["linked"] is True
    assert data["source_file_id"] == source_file_id
    assert f"fileId={source_file_id}" in data["evidence_path"]
    assert data["source_file"]["filename"] == "invoice.pdf"


def test_ingest_example_endpoint():
    headers, ledger_id = create_ledger_headers(client, "ingest_example", "13800139204")
    response = client.get(f"/api/files/ingest/example?ledger_id={ledger_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "curl_example" in data
    assert "cli_example" in data
    assert str(ledger_id) in data["curl_example"]
