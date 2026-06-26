import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import ChartOfAccounts, Counterparty, ImportJob, Organization, SourceFile
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


def test_ledger_files_can_filter_by_ledger_id(client):
    with next(app.dependency_overrides[get_db]()) as db:
        org = Organization(name="测试企业")
        db.add(org)
        db.flush()
        job_1 = ImportJob(organization_id=org.id, ledger_id=101)
        job_2 = ImportJob(organization_id=org.id, ledger_id=202)
        db.add_all([job_1, job_2])
        db.flush()
        db.add_all([
            SourceFile(
                organization_id=org.id,
                import_job_id=job_1.id,
                ledger_id=101,
                filename="A公司发票.pdf",
                file_type="pdf",
                storage_path="/tmp/a.pdf",
                text_extract_status="completed",
            ),
            SourceFile(
                organization_id=org.id,
                import_job_id=job_2.id,
                ledger_id=202,
                filename="B公司合同.pdf",
                file_type="pdf",
                storage_path="/tmp/b.pdf",
                text_extract_status="pending",
            ),
        ])
        db.commit()

    response = client.get("/api/files?ledger_id=101")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["ledger_id"] == 101
    assert data[0]["filename"] == "A公司发票.pdf"


def test_file_matches_and_binds_counterparty_context(client):
    with next(app.dependency_overrides[get_db]()) as db:
        org = Organization(name="测试企业")
        db.add(org)
        db.flush()
        job = ImportJob(organization_id=org.id, ledger_id=1)
        cp_auto = Counterparty(name="上海客户A", role="customer")
        cp_manual = Counterparty(name="北京客户B", role="customer")
        db.add_all([job, cp_auto, cp_manual])
        db.flush()
        source_file = SourceFile(
            organization_id=org.id,
            import_job_id=job.id,
            ledger_id=1,
            filename="6月服务费发票.pdf",
            file_type="pdf",
            storage_path="/tmp/service.pdf",
            text_extract_status="completed",
            extracted_text=json.dumps({
                "parse_feedback": {"summary": "上海客户A 6月服务费发票", "counterparty": "上海客户A"},
                "raw_text_preview": "上海客户A 6月服务费发票",
            }, ensure_ascii=False),
        )
        db.add(source_file)
        db.commit()
        file_id = source_file.id
        manual_id = cp_manual.id

    listing = client.get("/api/files?ledger_id=1")
    assert listing.status_code == 200
    first = listing.json()[0]
    assert first["counterparty_name"] == "上海客户A"
    assert first["customer_context"]["match_source"] in {"解析摘要", "对方单位字段"}

    bind = client.post(f"/api/files/{file_id}/bind-counterparty", json={"counterparty_id": manual_id})
    assert bind.status_code == 200
    data = bind.json()
    assert data["counterparty_name"] == "北京客户B"
    assert data["customer_context"]["match_source"] == "手工选择"


def test_industry_template_preview_and_import_do_not_override_existing_account(client):
    with next(app.dependency_overrides[get_db]()) as db:
        db.add(
            ChartOfAccounts(
                code="1001",
                name="库存现金-用户已修改",
                category="asset",
                direction="debit",
                is_system=False,
            )
        )
        db.commit()

    templates = client.get("/api/coa/industry-templates")
    assert templates.status_code == 200
    assert {item["name"] for item in templates.json()} >= {"通用企业", "商贸企业", "制造企业", "服务业"}

    preview = client.get("/api/coa/industry-templates/general")
    assert preview.status_code == 200
    summary = preview.json()["summary"]
    assert summary["conflicts"] == 1
    assert summary["new"] > 0

    imported = client.post("/api/coa/industry-templates/general/import")
    assert imported.status_code == 200
    result = imported.json()
    assert result["summary"]["conflicts"] == 1

    accounts = client.get("/api/coa").json()
    cash_account = next(item for item in accounts if item["code"] == "1001")
    assert cash_account["name"] == "库存现金-用户已修改"
    assert any(item["code"] == "1002" for item in accounts)


def test_industry_template_import_is_scoped_to_selected_ledger(client):
    preview_ledger_a = client.get("/api/coa/industry-templates/general?ledger_id=101")
    assert preview_ledger_a.status_code == 200
    assert preview_ledger_a.json()["summary"]["new"] > 0

    imported_a = client.post("/api/coa/industry-templates/general/import?ledger_id=101")
    assert imported_a.status_code == 200
    assert imported_a.json()["summary"]["new"] > 0

    accounts_a = client.get("/api/coa?ledger_id=101")
    assert accounts_a.status_code == 200
    assert len(accounts_a.json()) > 0
    assert {item["ledger_id"] for item in accounts_a.json()} == {101}

    accounts_b_before = client.get("/api/coa?ledger_id=202")
    assert accounts_b_before.status_code == 200
    assert accounts_b_before.json() == []

    preview_ledger_b = client.get("/api/coa/industry-templates/general?ledger_id=202")
    assert preview_ledger_b.status_code == 200
    assert preview_ledger_b.json()["summary"]["new"] == imported_a.json()["summary"]["new"]

    imported_b = client.post("/api/coa/industry-templates/general/import?ledger_id=202")
    assert imported_b.status_code == 200
    assert imported_b.json()["summary"]["new"] == imported_a.json()["summary"]["new"]

    accounts_b_after = client.get("/api/coa?ledger_id=202")
    assert accounts_b_after.status_code == 200
    assert len(accounts_b_after.json()) == len(accounts_a.json())
    assert {item["ledger_id"] for item in accounts_b_after.json()} == {202}
