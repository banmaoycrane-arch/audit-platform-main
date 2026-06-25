from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import (
    AccountingEntry,
    AccountingPeriod,
    EntryTag,
    ImportJob,
    Organization,
    SourceFile,
)
from app.models.lifecycle_log import LifecycleLog
from app.db.session import Base, get_db
from app.main import app
from app.services.lifecycle_service import log_lifecycle_event


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


def test_lifecycle_log_uses_independent_session_without_committing_caller_transaction(client):
    _, TestingSessionLocal = client
    db = TestingSessionLocal()
    try:
        org = Organization(name="未提交业务")
        db.add(org)
        log = log_lifecycle_event(
            db=db,
            entity_type="import_job",
            entity_id=999,
            action="test_independent_log",
            previous_status=None,
            new_status="manual_entry",
            reason="验证日志独立提交",
            operator_id=None,
        )
        db.rollback()
    finally:
        db.close()

    check_db = TestingSessionLocal()
    try:
        assert check_db.query(Organization).filter(Organization.name == "未提交业务").first() is None
        persisted_log = check_db.get(LifecycleLog, log.id)
        assert persisted_log is not None
        assert persisted_log.action == "test_independent_log"
    finally:
        check_db.close()


def _seed(TestingSessionLocal):
    db = TestingSessionLocal()
    try:
        org = Organization(name="生成测试", fiscal_year=2026)
        db.add(org)
        db.flush()
        job = ImportJob(organization_id=org.id, status="completed", entry_count=2, file_count=0)
        db.add(job)
        db.flush()
        db.add(
            SourceFile(
                organization_id=org.id,
                import_job_id=job.id,
                filename="银行流水.xlsx",
                file_type="bank_statement",
                storage_path="test/bank_statement.xlsx",
            )
        )
        db.add(
            SourceFile(
                organization_id=org.id,
                import_job_id=job.id,
                filename="销售合同.pdf",
                file_type="contract",
                storage_path="test/contract.pdf",
            )
        )
        period = AccountingPeriod(
            organization_id=org.id,
            period_code="2026-01",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            status="open",
        )
        db.add(period)
        db.add(
            AccountingEntry(
                organization_id=org.id,
                import_job_id=job.id,
                voucher_no="原-001",
                entry_line_no=1,
                voucher_date=date(2025, 12, 30),  # 越界
                summary="收到 A公司 货款",
                account_code="1002",
                account_name="银行存款",
                debit_amount=Decimal("1000"),
                credit_amount=Decimal("0"),
                counterparty="A公司",
            )
        )
        db.add(
            AccountingEntry(
                organization_id=org.id,
                import_job_id=job.id,
                voucher_no="原-001",
                entry_line_no=2,
                voucher_date=date(2025, 12, 30),
                summary="销项税额 增值税",
                account_code="222101",
                account_name="应交税费-应交增值税-销项税额",
                debit_amount=Decimal("0"),
                credit_amount=Decimal("130"),
                counterparty=None,
            )
        )
        db.commit()
        return job.id, period.id
    finally:
        db.close()


def _seed_source_files(TestingSessionLocal, files: list[dict]):
    db = TestingSessionLocal()
    try:
        org = Organization(name="资料充分性测试", fiscal_year=2026)
        db.add(org)
        db.flush()
        job = ImportJob(
            organization_id=org.id,
            status="parsed",
            source_type="source_documents",
            file_count=len(files),
            entry_count=0,
        )
        db.add(job)
        db.flush()
        period = AccountingPeriod(
            organization_id=org.id,
            period_code="2026-02",
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 28),
            status="open",
        )
        db.add(period)
        for index, file_data in enumerate(files, start=1):
            db.add(
                SourceFile(
                    organization_id=org.id,
                    import_job_id=job.id,
                    filename=file_data["filename"],
                    file_type=file_data["file_type"],
                    storage_path=f"test/evidence_{index}",
                    extracted_text=file_data.get("extracted_text"),
                )
            )
        db.commit()
        return job.id, period.id
    finally:
        db.close()


def test_generate_entries_requires_period(client):
    test_client, _ = client
    resp = test_client.post(
        "/api/import-jobs/9999/generate-entries",
        json={"period_id": 1},
    )
    assert resp.status_code == 404


def test_invoice_only_generates_staging_draft_with_accounts_receivable(client):
    test_client, TestingSessionLocal = client
    job_id, period_id = _seed_source_files(
        TestingSessionLocal,
        [{"filename": "销项发票.pdf", "file_type": "invoice"}],
    )

    resp = test_client.post(
        f"/api/import-jobs/{job_id}/generate-entries",
        json={"period_id": period_id},
    )

    assert resp.status_code == 200
    drafts = resp.json()
    assert len(drafts) == 3
    metadata = drafts[0]["metadata"]
    assert metadata["evidence_status"] == "partial"
    assert metadata["is_blocked"] is False
    assert metadata["accounting_flow"] == "accrual_only"
    assert metadata["accounting_judgment_policy"] == "compliant_default"
    assert "银行流水" in metadata["missing_evidence"]
    assert "销项税" in metadata["missing_reason"] or "应收" in metadata["missing_reason"]
    account_codes = {draft["account_code"] for draft in drafts}
    assert "1122" in account_codes
    assert "6001" in account_codes
    assert "22210107" in account_codes
    assert "1002" not in account_codes
    assert all(draft["metadata"].get("posting_phase") in {"accrual", "tax_invoice"} for draft in drafts)

    commit = test_client.post(
        f"/api/import-jobs/{job_id}/commit-entries",
        json={"period_id": period_id, "drafts": drafts},
    )
    assert commit.status_code == 200
    assert commit.json()["count"] == 3

    db = TestingSessionLocal()
    try:
        assert db.query(AccountingEntry).filter(AccountingEntry.import_job_id == job_id).count() == 3
    finally:
        db.close()


def test_invoice_with_prepaid_signal_uses_prepaid_account(client):
    test_client, TestingSessionLocal = client
    job_id, period_id = _seed_source_files(
        TestingSessionLocal,
        [{"filename": "预收款销项发票.pdf", "file_type": "invoice"}],
    )

    resp = test_client.post(
        f"/api/import-jobs/{job_id}/generate-entries",
        json={"period_id": period_id, "accounting_judgment_policy": "compliant_default"},
    )

    assert resp.status_code == 200
    drafts = resp.json()
    assert any(draft["account_code"] == "2203" for draft in drafts)


def test_invoice_with_outbound_compliant_generates_vat_only_invoice(client):
    test_client, TestingSessionLocal = client
    job_id, period_id = _seed_source_files(
        TestingSessionLocal,
        [
            {"filename": "销项发票.pdf", "file_type": "invoice"},
            {"filename": "销售出库单.pdf", "file_type": "inventory_out"},
        ],
    )

    resp = test_client.post(
        f"/api/import-jobs/{job_id}/generate-entries",
        json={"period_id": period_id, "accounting_judgment_policy": "compliant_default"},
    )

    assert resp.status_code == 200
    drafts = resp.json()
    invoice_drafts = [d for d in drafts if d["metadata"].get("source_evidence_type") == "invoice"]
    outbound_drafts = [d for d in drafts if d["metadata"].get("source_evidence_type") == "inventory_out"]
    assert len(invoice_drafts) == 2
    assert len(outbound_drafts) >= 2
    assert {d["account_code"] for d in invoice_drafts} == {"1122", "22210107"}
    assert "6001" not in {d["account_code"] for d in invoice_drafts}
    assert any(d["metadata"].get("invoice_role") == "vat_only_after_outbound" for d in invoice_drafts)


def test_counterparty_first_with_outbound_still_confirms_revenue_on_invoice(client):
    test_client, TestingSessionLocal = client
    job_id, period_id = _seed_source_files(
        TestingSessionLocal,
        [
            {"filename": "销项发票.pdf", "file_type": "invoice"},
            {"filename": "销售出库单.pdf", "file_type": "inventory_out"},
        ],
    )

    resp = test_client.post(
        f"/api/import-jobs/{job_id}/generate-entries",
        json={"period_id": period_id, "accounting_judgment_policy": "counterparty_first"},
    )

    assert resp.status_code == 200
    drafts = resp.json()
    invoice_drafts = [d for d in drafts if d["metadata"].get("source_evidence_type") == "invoice"]
    assert "6001" in {d["account_code"] for d in invoice_drafts}
    assert not any(d["metadata"].get("source_evidence_type") == "inventory_out" for d in drafts)


def test_invoice_with_matching_bank_statement_uses_accrual_then_collection(client):
    test_client, TestingSessionLocal = client
    job_id, period_id = _seed_source_files(
        TestingSessionLocal,
        [
            {"filename": "销项发票.pdf", "file_type": "invoice"},
            {"filename": "收款银行流水.xlsx", "file_type": "bank_statement"},
        ],
    )

    resp = test_client.post(
        f"/api/import-jobs/{job_id}/generate-entries",
        json={"period_id": period_id},
    )

    assert resp.status_code == 200
    drafts = resp.json()
    assert len(drafts) == 5
    assert all(draft["metadata"]["evidence_status"] == "sufficient" for draft in drafts)
    assert all(draft["metadata"]["is_blocked"] is False for draft in drafts)
    assert all(draft["metadata"]["accounting_flow"] == "accrual_then_collection" for draft in drafts)

    accrual_drafts = [d for d in drafts if d["metadata"].get("posting_phase") in {"accrual", "tax_invoice"}]
    collection_drafts = [d for d in drafts if d["metadata"].get("posting_phase") == "collection"]
    assert len(accrual_drafts) == 3
    assert len(collection_drafts) == 2
    assert {d["account_code"] for d in accrual_drafts} == {"1122", "6001", "22210107"}
    assert {d["account_code"] for d in collection_drafts} == {"1002", "1122"}
    assert not any(d["account_code"] == "1002" and d["metadata"].get("posting_phase") == "accrual" for d in drafts)


def test_bank_only_generates_blocked_draft_and_requires_business_document(client):
    test_client, TestingSessionLocal = client
    job_id, period_id = _seed_source_files(
        TestingSessionLocal,
        [{"filename": "银行流水.xlsx", "file_type": "bank_statement"}],
    )

    resp = test_client.post(
        f"/api/import-jobs/{job_id}/generate-entries",
        json={"period_id": period_id},
    )

    assert resp.status_code == 200
    drafts = resp.json()
    assert len(drafts) == 1
    metadata = drafts[0]["metadata"]
    assert metadata["evidence_status"] == "insufficient"
    assert metadata["is_blocked"] is True
    assert metadata["missing_evidence"] == ["合同", "订单", "结算单"]
    assert "不能单独证明业务性质" in metadata["missing_reason"]
    assert metadata["suggested_actions"] == ["请补充合同", "请补充订单", "请补充结算单"]
    assert drafts[0]["account_code"] == ""
    assert drafts[0]["account_name"] == "待补充资料确认"


def test_generate_drafts_apply_rules(client):
    test_client, TestingSessionLocal = client
    job_id, period_id = _seed(TestingSessionLocal)

    resp = test_client.post(
        f"/api/import-jobs/{job_id}/generate-entries",
        json={"period_id": period_id},
    )
    assert resp.status_code == 200
    drafts = resp.json()
    assert len(drafts) == 2

    # 银行存款行 → 银字
    bank_draft = next(d for d in drafts if d["account_code"] == "1002")
    assert bank_draft["voucher_no"].startswith("银-")
    # 期间夹紧
    assert bank_draft["voucher_date"] == "2026-01-01"
    assert bank_draft["metadata"]["date_clamped"] is True
    # 摘要按规则拼装且包含对方单位
    assert "A公司" in bank_draft["summary"]

    # 应交税费行 → 应识别销项税额、摘要、细分科目和原始资料 tag
    tax_draft = next(d for d in drafts if d["account_code"] == "222101")
    tag_types = {t["tag_type"] for t in tax_draft["tags"]}
    assert "tax_subitem" in tag_types
    assert "summary_keyword" in tag_types
    assert "account_detail_semantic" in tag_types
    assert "source_document" in tag_types
    assert "source_file" in tag_types
    assert "evidence_type" in tag_types

    bank_tag_values = {t["tag_value"] for t in bank_draft["tags"]}
    assert "A公司" in bank_tag_values
    assert "货款" in bank_tag_values


def test_commit_drafts_persists(client):
    test_client, TestingSessionLocal = client
    job_id, period_id = _seed(TestingSessionLocal)

    drafts_resp = test_client.post(
        f"/api/import-jobs/{job_id}/generate-entries",
        json={"period_id": period_id},
    )
    drafts = drafts_resp.json()

    commit = test_client.post(
        f"/api/import-jobs/{job_id}/commit-entries",
        json={"period_id": period_id, "drafts": drafts},
    )
    assert commit.status_code == 200
    payload = commit.json()
    assert payload["count"] == len(drafts)

    db = TestingSessionLocal()
    try:
        new_entries = (
            db.query(AccountingEntry)
            .filter(AccountingEntry.id.in_(payload["entry_ids"]))
            .order_by(AccountingEntry.voucher_no, AccountingEntry.entry_line_no)
            .all()
        )
        assert len(new_entries) == len(drafts)
        # entry_line_no 同凭证号下从 1 递增
        first = new_entries[0]
        assert first.entry_line_no == 1
        # tag 写入
        tags = (
            db.query(EntryTag)
            .filter(EntryTag.entry_id.in_([e.id for e in new_entries]))
            .all()
        )
        tag_pairs = {(t.tag_type, t.tag_value) for t in tags}
        assert any(t.tag_type == "tax_subitem" for t in tags)
        assert ("summary_keyword", "货款") in tag_pairs
        assert any(t.tag_type == "account_detail_semantic" for t in tags)
        assert any(t.tag_type == "counterparty" and t.tag_value == "A公司" for t in tags)
        assert any(t.tag_type == "source_file" and str(t.tag_value).startswith("source_file:") for t in tags)
        assert any(t.tag_type == "source_document" for t in tags)
        assert any(t.tag_type == "evidence_type" and t.tag_value in {"bank", "contract"} for t in tags)
        # vector_pending=True 表示尚未同步向量库
        assert all(t.vector_pending for t in tags)
        assert any(t.tag_type == "source" and t.tag_value == "source:ai_generated" for t in tags)
    finally:
        db.close()


def test_ai_draft_manual_switch_log_records_audit_objective_gap(client):
    test_client, TestingSessionLocal = client
    job_id, period_id = _seed(TestingSessionLocal)
    payload = {
        "period_id": period_id,
        "reason": "原始资料不能充分识别业务，真实性、准确性、截止性、充分性结论不足，转人工补充。",
        "recognized_evidence": [{"filename": "销项发票.pdf", "evidence_type": "invoice"}],
        "manual_fields": ["account_code", "counterparty"],
        "draft_metadata": {
            "evidence_status": "insufficient",
            "missing_evidence": ["银行流水"],
            "current_recognized_evidence": [{"filename": "销项发票.pdf"}],
        },
    }

    resp = test_client.post(
        f"/api/import-jobs/{job_id}/ai-draft/manual-switch-log",
        json=payload,
    )
    assert resp.status_code == 200
    assert resp.json()["action"] == "ai_draft_switched_to_manual"

    db = TestingSessionLocal()
    try:
        log = db.query(LifecycleLog).filter(LifecycleLog.entity_id == job_id).one()
        assert log.entity_type == "import_job"
        assert log.action == "ai_draft_switched_to_manual"
        assert log.previous_status == "ai_draft"
        assert log.new_status == "manual_entry"
        assert log.operator_id is None
        assert "真实性、准确性、截止性、充分性" in (log.reason or "")
        assert log.log_metadata["recognized_evidence"] == payload["recognized_evidence"]
        assert log.log_metadata["manual_fields"] == payload["manual_fields"]
        assert log.log_metadata["original_draft_metadata"] == payload["draft_metadata"]
        assert log.log_metadata["user"]["operator"] == "current_user_placeholder"
        assert "审计目的未达到" in log.log_metadata["audit_objective_note"]
    finally:
        db.close()



def test_commit_drafts_extracts_auxiliary_and_source_tags_from_metadata(client):
    test_client, TestingSessionLocal = client
    job_id, period_id = _seed(TestingSessionLocal)
    drafts = [
        {
            "voucher_no": "记-辅助-001",
            "voucher_date": "2026-01-15",
            "summary": "支付研发项目服务费",
            "account_code": "660201",
            "account_name": "管理费用-服务费",
            "debit_amount": 100,
            "credit_amount": 0,
            "counterparty": "服务商B",
            "entry_line_no": 1,
            "metadata": {
                "source": "ai_generated",
                "evidence_status": "sufficient",
                "is_blocked": False,
                "project": "研发项目A",
                "department": "研发部",
                "source_file_id": 88,
                "source_evidence_type": "contract",
                "current_recognized_evidence": [
                    {"id": 88, "filename": "研发服务合同.pdf", "evidence_type": "contract"}
                ],
            },
            "tags": [],
        }
    ]

    commit = test_client.post(
        f"/api/import-jobs/{job_id}/commit-entries",
        json={"period_id": period_id, "drafts": drafts},
    )

    assert commit.status_code == 200
    entry_id = commit.json()["entry_ids"][0]
    db = TestingSessionLocal()
    try:
        tags = db.query(EntryTag).filter(EntryTag.entry_id == entry_id).all()
        tag_pairs = {(tag.tag_type, tag.tag_value) for tag in tags}
        assert ("summary_keyword", "服务费") in tag_pairs
        assert ("account_detail_semantic", "服务费") in tag_pairs
        assert ("counterparty", "服务商B") in tag_pairs
        assert ("auxiliary_accounting", "project:研发项目A") in tag_pairs
        assert ("auxiliary_accounting", "department:研发部") in tag_pairs
        assert ("source_file", "source_file:88") in tag_pairs
        assert ("source_document", "研发服务合同.pdf") in tag_pairs
        assert ("evidence_type", "contract") in tag_pairs
        assert all(tag.vector_pending for tag in tags)
    finally:
        db.close()


def test_commit_manual_entries_persists_with_source_tag(client):
    test_client, TestingSessionLocal = client
    job_id, period_id = _seed(TestingSessionLocal)
    db = TestingSessionLocal()
    try:
        job = db.get(ImportJob, job_id)
        job.entry_count = 0
        db.commit()
    finally:
        db.close()

    drafts = [
        {
            "voucher_no": "记-001",
            "voucher_date": "2026-01-10",
            "summary": "收到客户货款",
            "account_code": "1002",
            "account_name": "银行存款",
            "debit_amount": 1000,
            "credit_amount": 0,
            "counterparty": "A公司",
            "entry_line_no": 1,
            "metadata": {"source": "manual_entry"},
            "tags": [],
        },
        {
            "voucher_no": "记-001",
            "voucher_date": "2026-01-10",
            "summary": "收到客户货款",
            "account_code": "1122",
            "account_name": "应收账款",
            "debit_amount": 0,
            "credit_amount": 1000,
            "counterparty": "A公司",
            "entry_line_no": 2,
            "metadata": {"source": "manual_entry"},
            "tags": [],
        },
    ]

    resp = test_client.post(
        "/api/import-jobs/manual-entries",
        json={"period_id": period_id, "drafts": drafts, "organization_name": "手工录入测试"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 2
    assert payload["job_id"]

    entries_resp = test_client.get(f"/api/entries?import_job_id={payload['job_id']}")
    assert entries_resp.status_code == 200
    entries = entries_resp.json()
    assert len(entries) == 2
    assert {entry["account_code"] for entry in entries} == {"1002", "1122"}

    db = TestingSessionLocal()
    try:
        source_tags = (
            db.query(EntryTag)
            .filter(EntryTag.entry_id.in_(payload["entry_ids"]))
            .filter(EntryTag.tag_type == "source")
            .all()
        )
        assert len(source_tags) == 2
        assert {tag.tag_value for tag in source_tags} == {"source:manual_entry"}
        all_tags = db.query(EntryTag).filter(EntryTag.entry_id.in_(payload["entry_ids"])).all()
        tag_pairs = {(tag.tag_type, tag.tag_value) for tag in all_tags}
        assert ("summary_keyword", "货款") in tag_pairs
        assert ("counterparty", "A公司") in tag_pairs
        manual_job = db.get(ImportJob, payload["job_id"])
        assert manual_job.source_type == "manual_entry"
        assert manual_job.entry_count == 2
    finally:
        db.close()


def test_commit_manual_entries_ignores_ai_blocked_metadata(client):
    test_client, TestingSessionLocal = client
    _, period_id = _seed(TestingSessionLocal)
    drafts = [
        {
            "voucher_no": "记-人工-001",
            "voucher_date": "2026-01-12",
            "summary": "人工确认收到客户货款",
            "account_code": "1002",
            "account_name": "银行存款",
            "debit_amount": 1000,
            "credit_amount": 0,
            "counterparty": "A公司",
            "entry_line_no": 1,
            "metadata": {
                "source": "manual_entry",
                "evidence_status": "insufficient",
                "is_blocked": True,
                "missing_evidence": ["银行流水"],
                "missing_reason": "AI 草稿资料不足",
            },
            "tags": [],
        },
        {
            "voucher_no": "记-人工-001",
            "voucher_date": "2026-01-12",
            "summary": "人工确认收到客户货款",
            "account_code": "1122",
            "account_name": "应收账款",
            "debit_amount": 0,
            "credit_amount": 1000,
            "counterparty": "A公司",
            "entry_line_no": 2,
            "metadata": {
                "source": "manual_entry",
                "evidence_status": "insufficient",
                "is_blocked": True,
                "missing_evidence": ["银行流水"],
                "missing_reason": "AI 草稿资料不足",
            },
            "tags": [],
        },
    ]

    resp = test_client.post(
        "/api/import-jobs/manual-entries",
        json={"period_id": period_id, "drafts": drafts, "organization_name": "手工录入测试"},
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["count"] == 2

    db = TestingSessionLocal()
    try:
        source_tags = (
            db.query(EntryTag)
            .filter(EntryTag.entry_id.in_(payload["entry_ids"]))
            .filter(EntryTag.tag_type == "source")
            .all()
        )
        assert {tag.tag_value for tag in source_tags} == {"source:manual_entry"}
    finally:
        db.close()


def test_commit_manual_entries_returns_business_error_when_unbalanced(client):
    test_client, TestingSessionLocal = client
    _, period_id = _seed(TestingSessionLocal)
    drafts = [
        {
            "voucher_no": "记-人工-002",
            "voucher_date": "2026-01-12",
            "summary": "人工确认收到客户货款",
            "account_code": "1002",
            "account_name": "银行存款",
            "debit_amount": 1000,
            "credit_amount": 0,
            "counterparty": "A公司",
            "entry_line_no": 1,
            "metadata": {"source": "manual_entry"},
            "tags": [],
        },
        {
            "voucher_no": "记-人工-002",
            "voucher_date": "2026-01-12",
            "summary": "人工确认收到客户货款",
            "account_code": "1122",
            "account_name": "应收账款",
            "debit_amount": 0,
            "credit_amount": 900,
            "counterparty": "A公司",
            "entry_line_no": 2,
            "metadata": {"source": "manual_entry"},
            "tags": [],
        },
    ]

    resp = test_client.post(
        "/api/import-jobs/manual-entries",
        json={"period_id": period_id, "drafts": drafts, "organization_name": "手工录入测试"},
    )

    assert resp.status_code == 400
    assert "人工凭证借贷不平衡" in resp.json()["detail"]

    db = TestingSessionLocal()
    try:
        manual_jobs = db.query(ImportJob).filter(ImportJob.source_type == "manual_entry").all()
        assert manual_jobs == []
    finally:
        db.close()
