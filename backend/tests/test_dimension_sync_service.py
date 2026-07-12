"""维度同步与待处理队列测试。"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.db.models import BankAccount, ImportJob, Ledger, Organization, StagingAccountingEntry, Team
from app.services.audit.dimension_sync_service import enrich_tags_from_master, sync_dimension_value_to_master
from app.services.audit.structured_import_service import build_dimension_pending_queue


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_job_with_staging(db):
    org = Organization(name="测试企业")
    db.add(org)
    db.flush()
    team = Team(name="测试团队")
    db.add(team)
    db.flush()
    ledger = Ledger(name="测试账簿", team_id=team.id)
    db.add(ledger)
    db.flush()
    job = ImportJob(
        organization_id=org.id,
        ledger_id=ledger.id,
        source_type="ledger_day_book",
        status="preview",
    )
    db.add(job)
    db.flush()
    row = StagingAccountingEntry(
        import_job_id=job.id,
        organization_id=org.id,
        ledger_id=ledger.id,
        voucher_no="记-001",
        summary="测试",
        account_code="100202",
        account_name="招行",
        resolved_account_code="1002",
        resolved_account_name="银行存款",
        debit_amount=Decimal("100.00"),
        credit_amount=Decimal("0.00"),
        entry_tags_payload=[
            {
                "category_code": "account_detail",
                "tag_value": "招行",
                "display_name": "招行",
                "source_sub_code": "02",
                "name_standardized": False,
            }
        ],
        original_row={"_requires_llm_resolution": True},
    )
    db.add(row)
    db.commit()
    return job, ledger, row


def test_sync_dimension_value_to_master_creates_bank_account(db):
    _job, ledger, _row = _seed_job_with_staging(db)
    result = sync_dimension_value_to_master(
        db,
        ledger.id,
        category_code="account_detail",
        display_name="招商银行股份有限公司北京分行",
        tag_value="招行",
        source_sub_code="02",
        account_code="1002",
    )
    assert result["synced"] is True
    assert result["target"] == "bank_accounts"
    account = (
        db.query(BankAccount)
        .filter(BankAccount.ledger_id == ledger.id, BankAccount.source_sub_code == "02")
        .one()
    )
    assert account.account_name == "招商银行股份有限公司北京分行"


def test_enrich_tags_from_master_uses_bank_account_name(db):
    _job, ledger, _row = _seed_job_with_staging(db)
    db.add(
        BankAccount(
            ledger_id=ledger.id,
            bank_name="招商银行",
            account_no="6222",
            account_name="招商银行股份有限公司北京分行",
            coa_account_code="1002",
            source_sub_code="02",
        )
    )
    db.commit()
    enriched = enrich_tags_from_master(
        db,
        ledger.id,
        [
            {
                "category_code": "account_detail",
                "tag_value": "招行",
                "display_name": "招行",
                "source_sub_code": "02",
            }
        ],
        account_code="1002",
    )
    assert enriched[0]["display_name"] == "招商银行股份有限公司北京分行"
    assert enriched[0]["name_standardized"] is True


def test_build_dimension_pending_queue_includes_llm_and_non_standard(db):
    job, _ledger, _row = _seed_job_with_staging(db)
    queue = build_dimension_pending_queue(db, job.id)
    assert queue["summary"]["total"] >= 2
    types = {item["queue_type"] for item in queue["items"]}
    assert "non_standardized" in types
    assert "requires_llm" in types


def test_build_dimension_pending_queue_includes_mapping_trace(db):
    from app.services.audit.structured_import_service import bulk_update_dimension_display_name

    job, _ledger, _row = _seed_job_with_staging(db)
    bulk_update_dimension_display_name(
        db,
        job.id,
        account_code="1002",
        category_code="account_detail",
        tag_value="招行",
        display_name="招商银行股份有限公司北京分行",
        source_sub_code="02",
        mapped_by_user_id=1,
    )
    db.commit()

    queue = build_dimension_pending_queue(db, job.id)
    mapped = [i for i in queue["items"] if i["queue_type"] == "mapped"]
    assert len(mapped) == 1
    assert mapped[0]["original_display_name"] == "招行"
    assert mapped[0]["display_name"] == "招商银行股份有限公司北京分行"
    assert mapped[0].get("mapped_at")
    assert queue["summary"]["mapped"] == 1
    non_standard = [i for i in queue["items"] if i["queue_type"] == "non_standardized"]
    assert len(non_standard) == 0


def test_build_dimension_pending_queue_confirm_unchanged_display_name(db):
    """人工「确认无误」（名称未改）后应从待补全称队列移除。"""
    from app.services.audit.structured_import_service import bulk_update_dimension_display_name

    org = Organization(name="测试企业")
    db.add(org)
    db.flush()
    team = Team(name="测试团队")
    db.add(team)
    db.flush()
    ledger = Ledger(name="测试账簿", team_id=team.id)
    db.add(ledger)
    db.flush()
    job = ImportJob(
        organization_id=org.id,
        ledger_id=ledger.id,
        source_type="ledger_day_book",
        status="preview",
    )
    db.add(job)
    db.flush()
    court_name = "岚县人民法院"
    row = StagingAccountingEntry(
        import_job_id=job.id,
        organization_id=org.id,
        ledger_id=ledger.id,
        voucher_no="记-010",
        summary="预付",
        account_code="1123",
        account_name="预付账款",
        resolved_account_code="1123",
        resolved_account_name="预付账款",
        debit_amount=Decimal("1000.00"),
        credit_amount=Decimal("0.00"),
        entry_tags_payload=[
            {
                "category_code": "customer",
                "tag_value": court_name,
                "display_name": court_name,
                "source_sub_code": "01",
                "name_standardized": False,
            }
        ],
    )
    db.add(row)
    db.commit()

    before = build_dimension_pending_queue(db, job.id)
    assert any(i.get("display_name") == court_name for i in before["items"] if i["queue_type"] == "non_standardized")

    bulk_update_dimension_display_name(
        db,
        job.id,
        account_code="1123",
        category_code="customer",
        tag_value=court_name,
        display_name=court_name,
        source_sub_code="01",
        name_standardized=True,
        mapped_by_user_id=1,
    )
    db.commit()

    after = build_dimension_pending_queue(db, job.id)
    non_standard = [i for i in after["items"] if i["queue_type"] == "non_standardized"]
    assert all(i.get("display_name") != court_name for i in non_standard)


def test_build_dimension_pending_queue_skips_full_customer_names(db):
    org = Organization(name="测试企业")
    db.add(org)
    db.flush()
    team = Team(name="测试团队")
    db.add(team)
    db.flush()
    ledger = Ledger(name="测试账簿", team_id=team.id)
    db.add(ledger)
    db.flush()
    job = ImportJob(
        organization_id=org.id,
        ledger_id=ledger.id,
        source_type="ledger_day_book",
        status="preview",
    )
    db.add(job)
    db.flush()
    full_name = "山西龙城景辉工业技术科技有限公司"
    row = StagingAccountingEntry(
        import_job_id=job.id,
        organization_id=org.id,
        ledger_id=ledger.id,
        voucher_no="记-002",
        summary="销售",
        account_code="112201",
        account_name=f"应收账款-{full_name}",
        resolved_account_code="1122",
        resolved_account_name="应收账款",
        debit_amount=Decimal("1000.00"),
        credit_amount=Decimal("0.00"),
        entry_tags_payload=[
            {
                "category_code": "customer",
                "tag_value": full_name,
                "display_name": full_name,
                "source_sub_code": "01",
                "name_standardized": False,
            }
        ],
    )
    db.add(row)
    db.commit()

    queue = build_dimension_pending_queue(db, job.id)
    non_standard = [i for i in queue["items"] if i["queue_type"] == "non_standardized"]
    assert all(full_name not in (i.get("display_name") or "") for i in non_standard)


def test_build_dimension_pending_queue_skips_person_names(db):
    org = Organization(name="测试企业")
    db.add(org)
    db.flush()
    team = Team(name="测试团队")
    db.add(team)
    db.flush()
    ledger = Ledger(name="测试账簿", team_id=team.id)
    db.add(ledger)
    db.flush()
    job = ImportJob(
        organization_id=org.id,
        ledger_id=ledger.id,
        source_type="ledger_day_book",
        status="preview",
    )
    db.add(job)
    db.flush()
    row = StagingAccountingEntry(
        import_job_id=job.id,
        organization_id=org.id,
        ledger_id=ledger.id,
        voucher_no="记-003",
        summary="借款",
        account_code="122101",
        account_name="其他应收款-张悦",
        resolved_account_code="1221",
        resolved_account_name="其他应收款",
        debit_amount=Decimal("500.00"),
        credit_amount=Decimal("0.00"),
        entry_tags_payload=[
            {
                "category_code": "counterparty_object",
                "tag_value": "张悦",
                "display_name": "张悦",
                "source_sub_code": "01",
                "name_standardized": False,
            }
        ],
    )
    db.add(row)
    db.commit()

    queue = build_dimension_pending_queue(db, job.id)
    non_standard = [i for i in queue["items"] if i["queue_type"] == "non_standardized"]
    assert all(i.get("display_name") != "张悦" for i in non_standard)


def test_build_dimension_pending_queue_flags_surname_only_person(db):
    org = Organization(name="测试企业")
    db.add(org)
    db.flush()
    team = Team(name="测试团队")
    db.add(team)
    db.flush()
    ledger = Ledger(name="测试账簿", team_id=team.id)
    db.add(ledger)
    db.flush()
    job = ImportJob(
        organization_id=org.id,
        ledger_id=ledger.id,
        source_type="ledger_day_book",
        status="preview",
    )
    db.add(job)
    db.flush()
    row = StagingAccountingEntry(
        import_job_id=job.id,
        organization_id=org.id,
        ledger_id=ledger.id,
        voucher_no="记-004",
        summary="往来",
        account_code="224102",
        account_name="其他应付款-宋",
        resolved_account_code="2241",
        resolved_account_name="其他应付款",
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("300.00"),
        entry_tags_payload=[
            {
                "category_code": "counterparty_object",
                "tag_value": "宋",
                "display_name": "宋",
                "source_sub_code": "0220",
                "name_standardized": False,
            }
        ],
    )
    db.add(row)
    db.commit()

    queue = build_dimension_pending_queue(db, job.id)
    non_standard = [i for i in queue["items"] if i["queue_type"] == "non_standardized"]
    assert len(non_standard) == 1
    assert non_standard[0]["display_name"] == "宋"
    assert "只有姓氏" in non_standard[0]["message"]
