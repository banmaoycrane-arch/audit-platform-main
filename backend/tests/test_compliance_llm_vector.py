"""单张凭证合规审查：向量检索 + LLM 语义识别。"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Organization, StagingAccountingEntry
from app.db.session import Base
from app.services.audit.compliance_review_service import review_single_staging_voucher, review_staging_compliance


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _seed_balanced_voucher(db, *, job_id: int, org_id: int) -> None:
    db.add(
        StagingAccountingEntry(
            import_job_id=job_id,
            organization_id=org_id,
            voucher_no="记-100",
            voucher_date=date(2024, 3, 1),
            entry_line_no=1,
            summary="支付办公费",
            account_code="6602",
            account_name="管理费用",
            debit_amount=Decimal("500.00"),
            credit_amount=Decimal("0.00"),
            normalized_text="支付办公费 管理费用",
            entry_tags_payload=[{"category_code": "expense_type", "tag_value": "office", "display_name": "办公费"}],
            review_status="draft",
        )
    )
    db.add(
        StagingAccountingEntry(
            import_job_id=job_id,
            organization_id=org_id,
            voucher_no="记-100",
            voucher_date=date(2024, 3, 1),
            entry_line_no=2,
            summary="银行存款",
            account_code="1002",
            account_name="银行存款",
            debit_amount=Decimal("0.00"),
            credit_amount=Decimal("500.00"),
            normalized_text="银行存款",
            review_status="draft",
        )
    )


def test_single_voucher_compliance_scopes_only_target(db, monkeypatch):
    from app.db.models import ImportJob

    org = Organization(name="测试组织")
    db.add(org)
    db.flush()
    job = ImportJob(organization_id=org.id, source_type="ledger_day_book", status="preview")
    db.add(job)
    db.flush()
    _seed_balanced_voucher(db, job_id=job.id, org_id=org.id)
    db.add(
        StagingAccountingEntry(
            import_job_id=job.id,
            organization_id=org.id,
            voucher_no="记-200",
            voucher_date=date(2024, 3, 2),
            entry_line_no=1,
            summary="其他凭证",
            account_code="1001",
            account_name="库存现金",
            debit_amount=Decimal("10.00"),
            credit_amount=Decimal("0.00"),
            review_status="draft",
        )
    )
    db.commit()

    monkeypatch.setattr(
        "app.services.audit.compliance_review_service._find_similar_tag_references",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        "app.services.audit.compliance_review_service._llm_semantic_compliance",
        lambda *_args, **_kwargs: ("仅审查目标凭证", "info", "语义结论", {"engine": "llm", "llm_used": True}),
    )

    result = review_single_staging_voucher(db, job.id, "记-100|2024-03-01")
    assert result["scope"] == "single_voucher"
    assert result["reviewed_vouchers"] == 1
    assert result["items"][0]["voucher_no"] == "记-100"

    untouched = (
        db.query(StagingAccountingEntry)
        .filter(StagingAccountingEntry.import_job_id == job.id, StagingAccountingEntry.voucher_no == "记-200")
        .first()
    )
    assert untouched.compliance_hint is None


def test_llm_vector_compliance_merges_findings(db, monkeypatch):
    from app.db.models import ImportJob

    org = Organization(name="测试组织")
    db.add(org)
    db.flush()
    job = ImportJob(organization_id=org.id, source_type="ledger_day_book", status="preview")
    db.add(job)
    db.flush()
    _seed_balanced_voucher(db, job_id=job.id, org_id=org.id)
    db.commit()

    similar_refs = [
        {
            "score": 0.91,
            "category_code": "expense_type",
            "tag_value": "office",
            "display_name": "办公费",
            "voucher_no": "记-88",
            "summary": "采购办公用品",
        }
    ]

    monkeypatch.setattr(
        "app.services.audit.compliance_review_service._find_similar_tag_references",
        lambda *_args, **_kwargs: similar_refs,
    )

    llm_payload = {
        "compliant": False,
        "severity": "warning",
        "summary": "科目与摘要匹配度偏低",
        "findings": ["管理费用摘要过于笼统"],
        "similar_case_notes": "与记-88 相比缺少具体业务说明",
    }

    class FakeLlm:
        def __init__(self, settings=None, config=None):
            pass

        def is_configured(self):
            return True

        def chat(self, messages, temperature=0.2, **kwargs):
            return SimpleNamespace(available=True, content=json.dumps(llm_payload, ensure_ascii=False), error=None)

    monkeypatch.setattr(
        "app.services.doc_parsing.parser_engine.config_service.get_runtime_parser_engine_config",
        lambda _db: {"ai_base_url": "http://127.0.0.1:11434/v1", "ai_model": "qwen2.5:7b", "ai_api_key": None},
    )

    monkeypatch.setattr(
        "app.services.agent.llm_client_service.LlmClientService",
        FakeLlm,
    )

    result = review_staging_compliance(db, job.id, mode="each", voucher_nos=["记-100"], use_llm=True)
    item = result["items"][0]
    assert item["engine"] == "llm+vector"
    assert item["llm_used"] is True
    assert item["similar_tag_refs"] == similar_refs
    assert "科目与摘要匹配度偏低" in (item["compliance_hint"] or "")
    assert item["compliance_severity"] == "warning"

    rows = db.query(StagingAccountingEntry).filter(StagingAccountingEntry.voucher_no == "记-100").all()
    assert all(row.compliance_severity == "warning" for row in rows)


def test_same_voucher_no_different_dates_reviewed_separately(db, monkeypatch):
    """同一凭证号、不同日期应视为两张独立凭证，合规提示不能串在一起。"""
    from app.db.models import ImportJob

    org = Organization(name="测试组织")
    db.add(org)
    db.flush()
    job = ImportJob(organization_id=org.id, source_type="ledger_day_book", status="preview")
    db.add(job)
    db.flush()

    db.add(
        StagingAccountingEntry(
            import_job_id=job.id,
            organization_id=org.id,
            voucher_no="记-0007",
            voucher_date=date(2022, 6, 30),
            entry_line_no=1,
            summary="利息",
            account_code="6603",
            account_name="财务费用",
            debit_amount=Decimal("2111.04"),
            credit_amount=Decimal("0.00"),
            review_status="draft",
        )
    )
    db.add(
        StagingAccountingEntry(
            import_job_id=job.id,
            organization_id=org.id,
            voucher_no="记-0007",
            voucher_date=date(2022, 7, 1),
            entry_line_no=1,
            summary="大额采购",
            account_code="2202",
            account_name="沈阳冶矿重型设备有限公司",
            debit_amount=Decimal("150000.00"),
            credit_amount=Decimal("0.00"),
            review_status="draft",
        )
    )
    db.add(
        StagingAccountingEntry(
            import_job_id=job.id,
            organization_id=org.id,
            voucher_no="记-0007",
            voucher_date=date(2022, 7, 1),
            entry_line_no=2,
            summary="银行存款",
            account_code="1002",
            account_name="银行存款",
            debit_amount=Decimal("0.00"),
            credit_amount=Decimal("150000.00"),
            review_status="draft",
        )
    )
    db.commit()

    monkeypatch.setattr(
        "app.services.audit.compliance_review_service._find_similar_tag_references",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        "app.services.audit.compliance_review_service._llm_semantic_compliance",
        lambda _db, voucher, **kwargs: (kwargs["rule_hint"], kwargs["rule_severity"], None, {"engine": "rules_only", "llm_used": False}),
    )

    result = review_single_staging_voucher(db, job.id, "记-0007|2022-06-30", use_llm=True)
    item = result["items"][0]
    assert item["line_count"] == 1
    assert item["compliance_hint"] == "借贷不平衡"
    assert "沈阳冶矿重型设备有限公司" not in (item["compliance_hint"] or "")
    assert "存在大额分录" not in (item["compliance_hint"] or "")

    july_rows = (
        db.query(StagingAccountingEntry)
        .filter(
            StagingAccountingEntry.import_job_id == job.id,
            StagingAccountingEntry.voucher_date == date(2022, 7, 1),
        )
        .all()
    )
    assert all(row.compliance_hint is None for row in july_rows)


def test_rules_fallback_when_llm_unconfigured(db, monkeypatch):
    from app.db.models import ImportJob

    org = Organization(name="测试组织")
    db.add(org)
    db.flush()
    job = ImportJob(organization_id=org.id, source_type="ledger_day_book", status="preview")
    db.add(job)
    db.flush()
    _seed_balanced_voucher(db, job_id=job.id, org_id=org.id)
    db.commit()

    monkeypatch.setattr(
        "app.services.audit.compliance_review_service._find_similar_tag_references",
        lambda *_args, **_kwargs: [],
    )

    class FakeLlm:
        def __init__(self, settings=None, config=None):
            pass

        def is_configured(self):
            return False

        def chat(self, messages, temperature=0.2, **kwargs):
            return SimpleNamespace(available=False, content=None, error="not configured")

    monkeypatch.setattr(
        "app.services.agent.llm_client_service.LlmClientService",
        FakeLlm,
    )

    result = review_staging_compliance(db, job.id, mode="each", voucher_nos=["记-100"], use_llm=True)
    item = result["items"][0]
    assert item["llm_used"] is False
    assert item["engine"] == "rules_fallback"
    assert item["compliance_severity"] == "info"
