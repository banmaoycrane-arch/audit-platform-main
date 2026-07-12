import io
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes_imports import _import_reports
from app.db.models import AccountingEntry, Counterparty, EntryTag, StagingAccountingEntry, TagCategory
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


def _review_all_staging(test_client, job_id: int, review_status: str = "verified") -> dict:
    response = test_client.post(
        f"/api/import-jobs/{job_id}/preview-entries/review-all",
        json={"review_status": review_status},
    )
    assert response.status_code == 200
    return response.json()


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
    assert payload["job"]["status"] == "preview"
    assert payload["report"]["total_entries"] > 0
    assert payload["report"]["day_book_report"]["completeness_score"] > 0

    db = TestingSessionLocal()
    try:
        staging = db.query(StagingAccountingEntry).filter(StagingAccountingEntry.import_job_id == job_id).all()
        assert len(staging) > 0
        entries = db.query(AccountingEntry).filter(AccountingEntry.import_job_id == job_id).all()
        assert len(entries) == 0
    finally:
        db.close()

    _review_all_staging(test_client, job_id)
    confirm_response = test_client.post(f"/api/import-jobs/{job_id}/confirm")
    assert confirm_response.status_code == 200
    assert confirm_response.json()["entries_created"] > 0

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


def test_apply_period_mapping_on_staging_preview_job(client):
    """预览阶段（staging）应能完成期间映射，且确认入账前不落正式凭证。"""
    from app.db.models import Voucher

    test_client, TestingSessionLocal = client
    ledger_id = _seed_ledger(TestingSessionLocal)
    create_response = test_client.post(
        "/api/import-jobs",
        json={
            "organization_name": "期间映射测试企业",
            "source_type": "ledger_day_book",
            "ledger_id": ledger_id,
        },
        headers=test_client._auth_headers,
    )
    job_id = create_response.json()["id"]

    csv_text = "\n".join([
        "凭证号,日期,摘要,科目编码,科目名称,借方,贷方",
        "记-001,2026-01-03,办公费,6602,管理费用,100,0",
        "记-001,2026-01-03,银行存款,1002,银行存款,0,100",
        "记-002,2026-02-04,收入,6001,主营业务收入,0,200",
        "记-002,2026-02-04,银行存款,1002,银行存款,200,0",
    ])
    test_client.post(
        f"/api/import-jobs/{job_id}/files",
        files={"file": ("ledger-day-book.csv", io.BytesIO(csv_text.encode("utf-8-sig")), "text/csv")},
    )
    process_response = test_client.post(f"/api/import-jobs/{job_id}/process/sync")
    assert process_response.status_code == 200
    assert process_response.json()["job"]["status"] == "preview"

    mapping_response = test_client.post(
        f"/api/import-jobs/{job_id}/apply-period-mapping",
        json={"period_mapping_mode": "preserve_source"},
    )
    assert mapping_response.status_code == 200
    mapping = mapping_response.json()
    assert mapping["assigned_voucher_count"] == 2
    assert mapping["staging_only"] is True
    assert len(mapping["used_period_codes"]) >= 2

    db = TestingSessionLocal()
    try:
        assert db.query(Voucher).filter(Voucher.import_job_id == job_id).count() == 0
        assert db.query(AccountingEntry).filter(AccountingEntry.import_job_id == job_id).count() == 0
    finally:
        db.close()


def test_compliance_review_api_each_mode(client):
    """合规审查 API 应能正常处理 staging 草稿（逐张审查）。"""
    test_client, TestingSessionLocal = client
    ledger_id = _seed_ledger(TestingSessionLocal)
    create_response = test_client.post(
        "/api/import-jobs",
        json={
            "organization_name": "合规审查测试企业",
            "source_type": "ledger_day_book",
            "ledger_id": ledger_id,
        },
        headers=test_client._auth_headers,
    )
    job_id = create_response.json()["id"]
    csv_text = "\n".join([
        "凭证号,日期,摘要,科目编码,科目名称,借方,贷方",
        "记-001,2026-01-03,办公费,6602,管理费用,100,0",
        "记-001,2026-01-03,银行存款,1002,银行存款,0,100",
    ])
    test_client.post(
        f"/api/import-jobs/{job_id}/files",
        files={"file": ("compliance.csv", io.BytesIO(csv_text.encode("utf-8-sig")), "text/csv")},
    )
    test_client.post(f"/api/import-jobs/{job_id}/process/sync")

    response = test_client.post(
        f"/api/import-jobs/{job_id}/preview-entries/compliance-review",
        json={"mode": "each"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["reviewed_vouchers"] == 1
    assert payload["skipped"] is False


def test_voucher_level_review_syncs_all_staging_lines(client):
    """复核状态应以整张凭证为单位同步到全部分录。"""
    test_client, TestingSessionLocal = client
    ledger_id = _seed_ledger(TestingSessionLocal)
    create_response = test_client.post(
        "/api/import-jobs",
        json={
            "organization_name": "凭证复核测试企业",
            "source_type": "ledger_day_book",
            "ledger_id": ledger_id,
        },
        headers=test_client._auth_headers,
    )
    job_id = create_response.json()["id"]
    csv_text = "\n".join([
        "凭证号,日期,摘要,科目编码,科目名称,借方,贷方",
        "记-001,2026-01-03,办公费,6602,管理费用,100,0",
        "记-001,2026-01-03,银行存款,1002,银行存款,0,100",
    ])
    test_client.post(
        f"/api/import-jobs/{job_id}/files",
        files={"file": ("review.csv", io.BytesIO(csv_text.encode("utf-8-sig")), "text/csv")},
    )
    test_client.post(f"/api/import-jobs/{job_id}/process/sync")

    preview = test_client.get(f"/api/import-jobs/{job_id}/preview-entries?limit=10&offset=0")
    assert preview.status_code == 200
    first_id = preview.json()["items"][0]["id"]

    patch = test_client.patch(
        f"/api/import-jobs/{job_id}/preview-entries/{first_id}",
        json={"review_status": "verified"},
    )
    assert patch.status_code == 200

    db = TestingSessionLocal()
    try:
        rows = db.query(StagingAccountingEntry).filter(StagingAccountingEntry.import_job_id == job_id).all()
        assert len(rows) == 2
        assert all(row.review_status == "verified" for row in rows)
    finally:
        db.close()

    stats = test_client.get(f"/api/import-jobs/{job_id}/preview-entries?limit=1&offset=0").json()["review_stats"]
    assert stats["total_vouchers"] == 1
    assert stats["verified_vouchers"] == 1
    assert stats["partial_vouchers"] == 0


def test_confirm_blocks_partial_or_unreviewed_vouchers(client):
    """部分复核或未复核凭证不得确认入账。"""
    test_client, TestingSessionLocal = client
    ledger_id = _seed_ledger(TestingSessionLocal)
    create_response = test_client.post(
        "/api/import-jobs",
        json={
            "organization_name": "确认校验测试企业",
            "source_type": "ledger_day_book",
            "ledger_id": ledger_id,
        },
        headers=test_client._auth_headers,
    )
    job_id = create_response.json()["id"]
    csv_text = "\n".join([
        "凭证号,日期,摘要,科目编码,科目名称,借方,贷方",
        "记-001,2026-01-03,办公费,6602,管理费用,100,0",
        "记-001,2026-01-03,银行存款,1002,银行存款,0,100",
        "记-002,2026-02-04,收入,6001,主营业务收入,0,200",
        "记-002,2026-02-04,银行存款,1002,银行存款,200,0",
    ])
    test_client.post(
        f"/api/import-jobs/{job_id}/files",
        files={"file": ("confirm-guard.csv", io.BytesIO(csv_text.encode("utf-8-sig")), "text/csv")},
    )
    test_client.post(f"/api/import-jobs/{job_id}/process/sync")

    unreviewed = test_client.post(f"/api/import-jobs/{job_id}/confirm")
    assert unreviewed.status_code == 400
    assert "复核" in unreviewed.json()["detail"]

    db = TestingSessionLocal()
    try:
        rows = db.query(StagingAccountingEntry).filter(StagingAccountingEntry.import_job_id == job_id).all()
        voucher_001 = [row for row in rows if row.voucher_no == "记-001"]
        voucher_001[0].review_status = "verified"
        db.commit()
    finally:
        db.close()

    partial = test_client.post(f"/api/import-jobs/{job_id}/confirm")
    assert partial.status_code == 400
    assert "部分复核" in partial.json()["detail"]

    _review_all_staging(test_client, job_id)
    ok = test_client.post(f"/api/import-jobs/{job_id}/confirm")
    assert ok.status_code == 200


def test_editing_verified_voucher_is_blocked(client):
    """已复核凭证的分录不可再修改。"""
    test_client, TestingSessionLocal = client
    ledger_id = _seed_ledger(TestingSessionLocal)
    create_response = test_client.post(
        "/api/import-jobs",
        json={
            "organization_name": "编辑锁定测试企业",
            "source_type": "ledger_day_book",
            "ledger_id": ledger_id,
        },
        headers=test_client._auth_headers,
    )
    job_id = create_response.json()["id"]
    csv_text = "\n".join([
        "凭证号,日期,摘要,科目编码,科目名称,借方,贷方",
        "记-001,2026-01-03,办公费,6602,管理费用,100,0",
        "记-001,2026-01-03,银行存款,1002,银行存款,0,100",
    ])
    test_client.post(
        f"/api/import-jobs/{job_id}/files",
        files={"file": ("edit-lock.csv", io.BytesIO(csv_text.encode("utf-8-sig")), "text/csv")},
    )
    test_client.post(f"/api/import-jobs/{job_id}/process/sync")
    _review_all_staging(test_client, job_id)

    preview = test_client.get(f"/api/import-jobs/{job_id}/preview-entries?limit=10&offset=0")
    entry_id = preview.json()["items"][0]["id"]
    blocked = test_client.patch(
        f"/api/import-jobs/{job_id}/preview-entries/{entry_id}",
        json={"summary": "修改摘要"},
    )
    assert blocked.status_code == 400
    assert "已复核" in blocked.json()["detail"]


def test_preview_vouchers_api_groups_by_voucher(client):
    """预览凭证列表应按整张凭证聚合，并支持筛选。"""
    test_client, TestingSessionLocal = client
    ledger_id = _seed_ledger(TestingSessionLocal)
    create_response = test_client.post(
        "/api/import-jobs",
        json={
            "organization_name": "凭证列表测试企业",
            "source_type": "ledger_day_book",
            "ledger_id": ledger_id,
        },
        headers=test_client._auth_headers,
    )
    job_id = create_response.json()["id"]
    csv_text = "\n".join([
        "凭证号,日期,摘要,科目编码,科目名称,借方,贷方",
        "记-001,2026-01-03,办公费,6602,管理费用,100,0",
        "记-001,2026-01-03,银行存款,1002,银行存款,0,100",
        "记-002,2026-02-04,收入,6001,主营业务收入,0,200",
        "记-002,2026-02-04,银行存款,1002,银行存款,200,0",
    ])
    test_client.post(
        f"/api/import-jobs/{job_id}/files",
        files={"file": ("vouchers.csv", io.BytesIO(csv_text.encode("utf-8-sig")), "text/csv")},
    )
    test_client.post(f"/api/import-jobs/{job_id}/process/sync")

    pending = test_client.get(f"/api/import-jobs/{job_id}/preview-vouchers?review_filter=pending")
    assert pending.status_code == 200
    payload = pending.json()
    assert payload["total"] == 2
    assert payload["review_stats"]["total_vouchers"] == 2

    group_key = payload["items"][0]["group_key"]
    lines = test_client.get(f"/api/import-jobs/{job_id}/preview-vouchers/{group_key}/lines")
    assert lines.status_code == 200
    assert len(lines.json()["items"]) == 2

    stats = test_client.get(f"/api/import-jobs/{job_id}/preview-voucher-stats")
    assert stats.status_code == 200
    stats_payload = stats.json()
    assert stats_payload["total_vouchers"] == 2
    assert stats_payload["total_lines"] == 4


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
        "记-002,2026-01-04,采购进项税,2221.01.01,应交税费-应交增值税-进项税额,11300,0,供应商B",
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
    assert payload["job"]["status"] == "preview"

    _review_all_staging(test_client, job_id)
    confirm_response = test_client.post(f"/api/import-jobs/{job_id}/confirm")
    assert confirm_response.status_code == 200

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


def test_audit_day_book_reimport_on_same_ledger_reuses_vouchers(client):
    """同一账簿再次导入时不应触发 vouchers(ledger_id, voucher_no) 唯一约束冲突。"""
    test_client, TestingSessionLocal = client
    ledger_id = _seed_ledger(TestingSessionLocal)
    project_id = _seed_audit_project(TestingSessionLocal, ledger_id)
    csv_text = "\n".join([
        "凭证号,日期,摘要,科目编码,科目名称,借方,贷方,对方单位",
        "记-001,2026-01-03,收到客户货款,1002,银行存款,12000,0,客户A",
        "记-001,2026-01-03,冲减应收账款,1122,应收账款,0,12000,客户A",
    ])

    def _create_and_process() -> int:
        create_response = test_client.post(
            "/api/import-jobs",
            json={
                "organization_name": "序时簿重复导入测试企业",
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
        upload_response = test_client.post(
            f"/api/import-jobs/{job_id}/files",
            files={"file": ("audit-day-book.csv", io.BytesIO(csv_text.encode("utf-8-sig")), "text/csv")},
        )
        assert upload_response.status_code == 200
        process_response = test_client.post(f"/api/import-jobs/{job_id}/process/sync")
        assert process_response.status_code == 200
        _review_all_staging(test_client, job_id)
        confirm_response = test_client.post(f"/api/import-jobs/{job_id}/confirm")
        assert confirm_response.status_code == 200
        return job_id

    first_job_id = _create_and_process()
    second_job_id = _create_and_process()
    assert first_job_id != second_job_id

    db = TestingSessionLocal()
    try:
        from app.db.models import Voucher

        vouchers = db.query(Voucher).filter(Voucher.ledger_id == ledger_id).all()
        assert len(vouchers) == 1
        assert vouchers[0].voucher_no == "记-001"

        entries = db.query(AccountingEntry).filter(AccountingEntry.ledger_id == ledger_id).all()
        assert len(entries) == 2
        assert {entry.import_job_id for entry in entries} == {first_job_id}
    finally:
        db.close()


def test_ledger_day_book_reimport_with_zero_padded_voucher_no(client):
    """记账模式序时簿重复导入时，零填充凭证号（记-0001）应复用已有凭证。"""
    test_client, TestingSessionLocal = client
    ledger_id = _seed_ledger(TestingSessionLocal)
    csv_text = "\n".join([
        "凭证号,日期,摘要,科目编码,科目名称,借方,贷方,对方单位",
        "记-0001,2026-01-03,收到客户货款,1002,银行存款,12000,0,客户A",
        "记-0001,2026-01-03,冲减应收账款,1122,应收账款,0,12000,客户A",
    ])

    def _create_and_process() -> int:
        create_response = test_client.post(
            "/api/import-jobs",
            json={
                "organization_name": "记账序时簿重复导入测试",
                "industry": "manufacturing",
                "fiscal_year": 2026,
                "source_type": "ledger_day_book",
                "ledger_id": ledger_id,
            },
            headers=test_client._auth_headers,
        )
        assert create_response.status_code == 200
        job_id = create_response.json()["id"]
        upload_response = test_client.post(
            f"/api/import-jobs/{job_id}/files",
            files={"file": ("ledger-day-book.csv", io.BytesIO(csv_text.encode("utf-8-sig")), "text/csv")},
        )
        assert upload_response.status_code == 200
        process_response = test_client.post(f"/api/import-jobs/{job_id}/process/sync")
        assert process_response.status_code == 200
        assert process_response.json()["job"]["status"] == "preview"
        _review_all_staging(test_client, job_id)
        confirm_response = test_client.post(f"/api/import-jobs/{job_id}/confirm")
        assert confirm_response.status_code == 200
        return job_id

    first_job_id = _create_and_process()
    second_job_id = _create_and_process()
    assert first_job_id != second_job_id

    db = TestingSessionLocal()
    try:
        from app.db.models import Voucher

        vouchers = db.query(Voucher).filter(Voucher.ledger_id == ledger_id).all()
        assert len(vouchers) == 1
        assert vouchers[0].voucher_no == "记-0001"

        entries = db.query(AccountingEntry).filter(AccountingEntry.ledger_id == ledger_id).all()
        assert len(entries) == 2
    finally:
        db.close()


def test_audit_day_book_reprocess_same_job_is_idempotent(client):
    """同一导入任务重复调用 process/sync 时不应重复落库或触发唯一约束冲突。"""
    test_client, TestingSessionLocal = client
    ledger_id = _seed_ledger(TestingSessionLocal)
    project_id = _seed_audit_project(TestingSessionLocal, ledger_id)
    create_response = test_client.post(
        "/api/import-jobs",
        json={
            "organization_name": "序时簿重复处理测试企业",
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
        "记-0001,2026-01-03,收到客户货款,1002,银行存款,12000,0,客户A",
        "记-0001,2026-01-03,冲减应收账款,1122,应收账款,0,12000,客户A",
    ])
    upload_response = test_client.post(
        f"/api/import-jobs/{job_id}/files",
        files={"file": ("audit-day-book.csv", io.BytesIO(csv_text.encode("utf-8-sig")), "text/csv")},
    )
    assert upload_response.status_code == 200

    first_process = test_client.post(f"/api/import-jobs/{job_id}/process/sync")
    assert first_process.status_code == 200
    second_process = test_client.post(f"/api/import-jobs/{job_id}/process/sync")
    assert second_process.status_code == 200

    _review_all_staging(test_client, job_id)
    confirm_response = test_client.post(f"/api/import-jobs/{job_id}/confirm")
    assert confirm_response.status_code == 200

    db = TestingSessionLocal()
    try:
        from app.db.models import Voucher

        staging = db.query(StagingAccountingEntry).filter(StagingAccountingEntry.import_job_id == job_id).all()
        assert len(staging) == 0
        entries = db.query(AccountingEntry).filter(AccountingEntry.import_job_id == job_id).all()
        vouchers = db.query(Voucher).filter(Voucher.ledger_id == ledger_id).all()
        assert len(entries) == 2
        assert len(vouchers) == 1
        assert vouchers[0].voucher_no == "记-0001"
    finally:
        db.close()
