import io
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes_imports import _import_reports
from app.db.models import AccountingEntry, Counterparty, EntryTag, TagCategory
from app.db.session import Base, get_db
from app.main import app
from app.models.ledger import Ledger
from app.models.team import Team


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
    monkeypatch.setattr("app.services.doc_parsing.import_service.safe_vector_store", lambda: None)
    monkeypatch.setattr("app.services.audit.risk_case_library.safe_vector_store", lambda: None)
    monkeypatch.setattr("app.services.audit.risk_rule_service.safe_vector_store", lambda: None)
    monkeypatch.setattr("app.services.audit.audit_day_book_service.safe_vector_store", lambda: None)
    monkeypatch.setattr("app.services.accounting.entry_tag_vector_service.safe_vector_store", lambda: None)
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


def _seed_ledger(TestingSessionLocal) -> int:
    db = TestingSessionLocal()
    try:
        team = Team(name="序时簿导入测试团队")
        db.add(team)
        db.flush()
        ledger = Ledger(name="序时簿导入测试账簿", team_id=team.id)
        db.add(ledger)
        db.commit()
        return ledger.id
    finally:
        db.close()


def _seed_audit_project(TestingSessionLocal, ledger_id: int) -> int:
    db = TestingSessionLocal()
    try:
        from app.models.project import Project
        from app.models.project_ledger import ProjectLedger

        ledger = db.query(Ledger).filter(Ledger.id == ledger_id).first()
        team_id = ledger.team_id if ledger else None

        project = Project(name="序时簿导入测试项目", type="audit", status="active", team_id=team_id)
        db.add(project)
        db.flush()

        project_ledger = ProjectLedger(project_id=project.id, ledger_id=ledger_id)
        db.add(project_ledger)
        db.commit()
        return project.id
    finally:
        db.close()


def test_audit_day_book_csv_import_creates_entries_tags_and_report(client):
    test_client, TestingSessionLocal = client
    ledger_id = _seed_ledger(TestingSessionLocal)
    project_id = _seed_audit_project(TestingSessionLocal, ledger_id)
    create_response = test_client.post(
        "/api/import-jobs",
        json={
            "organization_name": "序时簿导入测试企业",
            "industry": "manufacturing",
            "fiscal_year": 2026,
            "source_type": "audit_day_book",
            "ledger_id": ledger_id,
            "project_id": project_id,
        },
        headers=test_client._auth_headers,
    )
    assert create_response.status_code == 200
    job_id = create_response.json()["id"]

    csv_text = "\n".join([
        "凭证号,日期,摘要,科目编码,科目名称,借方,贷方,对方单位",
        "记-001,2026-01-03,收到客户货款,1002,银行存款,12000,0,客户A",
        "记-001,2026-01-03,冲减应收账款,1122,应收账款,0,12000,客户A",
    ])
    upload_response = test_client.post(
        f"/api/import-jobs/{job_id}/files",
        files={"file": ("audit-day-book.csv", io.BytesIO(csv_text.encode("utf-8-sig")), "text/csv")},
    )
    assert upload_response.status_code == 200
    assert upload_response.json()["file_type"] == "csv"

    process_response = test_client.post(f"/api/import-jobs/{job_id}/process/sync")

    assert process_response.status_code == 200
    payload = process_response.json()
    assert payload["job"]["status"] == "completed"
    assert payload["report"]["total_entries"] > 0
    assert payload["report"]["day_book_report"]["completeness_score"] > 0

    report_response = test_client.get(f"/api/import-jobs/{job_id}/report")
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["total_entries"] > 0
    assert report["day_book_report"]["completeness_score"] > 0

    db = TestingSessionLocal()
    try:
        entries = db.query(AccountingEntry).filter(AccountingEntry.import_job_id == job_id).all()
        assert len(entries) > 0
        assert {entry.account_name for entry in entries} == {"银行存款", "应收账款"}

        # 验证一级科目已保留，原科目名称保留审计追溯
        bank_entry = [e for e in entries if e.account_name == "银行存款"][0]
        assert bank_entry.resolved_account_code == "1002"
        assert bank_entry.resolved_account_name == "银行存款"

        # 验证往来单位已自动创建并关联
        counterparties = db.query(Counterparty).filter(Counterparty.name == "客户A").all()
        assert len(counterparties) == 1
        assert any(e.counterparty_id == counterparties[0].id for e in entries)
    finally:
        db.close()


def test_audit_day_book_csv_import_resolves_account_hierarchy(client):
    """测试科目层级解析：一级科目保留、辅助核算维度转 Tag、强制二级科目保留。"""
    test_client, TestingSessionLocal = client
    ledger_id = _seed_ledger(TestingSessionLocal)
    project_id = _seed_audit_project(TestingSessionLocal, ledger_id)
    create_response = test_client.post(
        "/api/import-jobs",
        json={
            "organization_name": "科目层级测试企业",
            "industry": "manufacturing",
            "fiscal_year": 2026,
            "source_type": "audit_day_book",
            "ledger_id": ledger_id,
            "project_id": project_id,
        },
        headers=test_client._auth_headers,
    )
    assert create_response.status_code == 200
    job_id = create_response.json()["id"]

    csv_text = "\n".join([
        "凭证号,日期,摘要,科目编码,科目名称,借方,贷方,对方单位",
        "记-001,2026-01-03,收到客户货款,1002.01,银行存款-基本户,12000,0,客户A",
        "记-001,2026-01-03,确认收入,6001.01,主营业务收入-产品X,0,12000,客户A",
        "记-002,2026-01-04,采购进项税,2221.01.01,应交税费-应交增值税-进项税额,1300,0,供应商B",
        "记-002,2026-01-04,支付货款,2202.01,应付账款-供应商B,0,11300,供应商B",
    ])
    upload_response = test_client.post(
        f"/api/import-jobs/{job_id}/files",
        files={"file": ("audit-day-book.csv", io.BytesIO(csv_text.encode("utf-8-sig")), "text/csv")},
    )
    assert upload_response.status_code == 200

    process_response = test_client.post(f"/api/import-jobs/{job_id}/process/sync")
    assert process_response.status_code == 200
    payload = process_response.json()
    assert payload["job"]["status"] == "completed"

    db = TestingSessionLocal()
    try:
        entries = db.query(AccountingEntry).filter(AccountingEntry.import_job_id == job_id).all()
        assert len(entries) == 4

        # 银行存款-基本户：应扁平化为 1002，并生成 product/account_detail Tag（根据映射为 product）
        bank_entry = [e for e in entries if e.account_code == "1002.01"][0]
        assert bank_entry.resolved_account_code == "1002"
        assert bank_entry.resolved_account_name == "银行存款"

        # 主营业务收入-产品X：应扁平化为 6001，并生成 product Tag
        revenue_entry = [e for e in entries if e.account_code == "6001.01"][0]
        assert revenue_entry.resolved_account_code == "6001"
        assert revenue_entry.resolved_account_name == "主营业务收入"
        revenue_tags = db.query(EntryTag).filter(EntryTag.entry_id == revenue_entry.id).all()
        assert any(t.tag_type == "product" and t.tag_value == "产品X" for t in revenue_tags)

        # 应交增值税进项税额：强制保留完整层级
        vat_entry = [e for e in entries if e.account_code == "2221.01.01"][0]
        assert vat_entry.resolved_account_code == "2221.01.01"
        assert vat_entry.resolved_account_name == "应交税费-应交增值税-进项税额"
        vat_tags = db.query(EntryTag).filter(EntryTag.entry_id == vat_entry.id).all()
        assert len(vat_tags) == 0

        # 应付账款-供应商B：应扁平化为 2202，并生成 supplier Tag
        payable_entry = [e for e in entries if e.account_code == "2202.01"][0]
        assert payable_entry.resolved_account_code == "2202"
        assert payable_entry.resolved_account_name == "应付账款"
        payable_tags = db.query(EntryTag).filter(EntryTag.entry_id == payable_entry.id).all()
        assert any(t.tag_type == "supplier" and t.tag_value == "供应商B" for t in payable_tags)

        # 验证 TagCategory 已自动创建
        categories = db.query(TagCategory).filter(TagCategory.ledger_id == ledger_id).all()
        category_codes = {cat.code for cat in categories}
        assert "product" in category_codes
        assert "supplier" in category_codes
    finally:
        db.close()
