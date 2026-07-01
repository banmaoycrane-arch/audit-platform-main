# -*- coding: utf-8 -*-
"""
智能标签、分析视图、向量服务测试。
"""
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.team import Team
from app.models.user import User
from app.services.analytics_service import (
    analyze_counterparty,
    analyze_project_cost,
    drill_down_counterparty,
)
from app.services.entry_tag_rules_engine import (
    TagSuggestion,
    apply_auto_tags_to_voucher_lines,
    suggest_tags_for_entry,
)
from app.db.models import AccountingEntry
from app.services.entry_tag_vector_service import EntryTagVectorService
from app.services.ledger_management_service import create_ledger
from app.services.tag_category_service import clear_category_cache
from app.services.voucher_service import VoucherEntryLine, create_voucher


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def ledger(db):
    clear_category_cache()
    team = Team(name="auto_tag_team", type="virtual")
    db.add(team)
    db.flush()

    user = User(username="auto_tag_user", phone="13800000004", team_id=team.id)
    db.add(user)
    db.flush()

    ledger = create_ledger(
        db,
        team_id=team.id,
        name="auto_tag_ledger",
        accounting_start_date=date(2026, 1, 1),
    )
    db.commit()
    return ledger


def test_suggest_tags_for_entry(db, ledger):
    entry = {
        "account_code": "1122",
        "account_name": "应收账款",
        "summary": "销售商品给山西岚县尚德鑫项目:审计项目2026",
        "debit_amount": 150000.00,
        "credit_amount": 0,
        "counterparty": "山西岚县尚德鑫",
    }
    suggestions = suggest_tags_for_entry(db, ledger.id, entry)

    categories = {s.category_code for s in suggestions}
    assert "counterparty" in categories
    assert "account_category" in categories
    assert "business_type" in categories
    assert "project" in categories
    assert "amount_scale" in categories

    counterparty_tag = next(s for s in suggestions if s.category_code == "counterparty")
    assert counterparty_tag.tag_value == "山西岚县尚德鑫"


def test_apply_auto_tags_to_voucher_lines(db, ledger):
    lines = [
        VoucherEntryLine(
            account_code="1122",
            account_name="应收账款",
            summary="销售商品给A公司",
            debit_amount=10000,
            credit_amount=0,
            counterparty="A公司",
        )
    ]
    apply_auto_tags_to_voucher_lines(db, ledger.id, lines)

    assert len(lines[0].tags) >= 2
    categories = {t["category_code"] for t in lines[0].tags}
    assert "counterparty" in categories
    assert "account_category" in categories


def test_create_voucher_auto_tags(db, ledger):
    lines = [
        VoucherEntryLine(
            account_code="1122",
            account_name="应收账款",
            summary="销售商品给B公司项目:测试项目",
            debit_amount=20000,
            credit_amount=0,
            counterparty="B公司",
        ),
        VoucherEntryLine(
            account_code="6001",
            account_name="主营业务收入",
            summary="销售商品给B公司",
            debit_amount=0,
            credit_amount=20000,
        ),
    ]

    voucher = create_voucher(
        db,
        ledger_id=ledger.id,
        organization_id=1,
        voucher_no="AUTO-001",
        voucher_date=date(2026, 1, 15),
        summary="自动标签测试",
        lines=lines,
        auto_commit=True,
    )

    db.refresh(voucher)
    entries = db.query(AccountingEntry).filter_by(voucher_id=voucher.id).order_by(AccountingEntry.entry_line_no).all()
    assert len(entries) == 2

    first_entry = entries[0]
    tags = first_entry.tags
    assert len(tags) >= 2
    categories = {t.category.code if t.category else t.tag_type for t in tags}
    assert "counterparty" in categories


def test_counterparty_analysis(db, ledger):
    # 创建测试凭证
    lines = [
        VoucherEntryLine(
            account_code="1122",
            account_name="应收账款",
            summary="销售给C公司",
            debit_amount=50000,
            credit_amount=0,
            counterparty="C公司",
        ),
        VoucherEntryLine(
            account_code="6001",
            account_name="主营业务收入",
            summary="销售给C公司",
            debit_amount=0,
            credit_amount=50000,
        ),
    ]
    create_voucher(
        db,
        ledger_id=ledger.id,
        organization_id=1,
        voucher_no="CA-001",
        voucher_date=date(2026, 1, 10),
        lines=lines,
        auto_commit=True,
    )

    db.expire_all()
    result = analyze_counterparty(db, ledger.id)
    assert len(result) == 1
    assert result[0]["counterparty"] == "C公司"
    assert result[0]["total_debit"] == 50000

    details = drill_down_counterparty(db, ledger.id, "C公司")
    assert len(details) == 1
    assert details[0]["counterparty"] == "C公司"


def test_project_cost_analysis(db, ledger):
    lines = [
        VoucherEntryLine(
            account_code="6602",
            account_name="管理费用",
            summary="项目:审计项目2026 差旅费",
            debit_amount=8000,
            credit_amount=0,
        ),
        VoucherEntryLine(
            account_code="1002",
            account_name="银行存款",
            summary="支付差旅费",
            debit_amount=0,
            credit_amount=8000,
        ),
    ]
    create_voucher(
        db,
        ledger_id=ledger.id,
        organization_id=1,
        voucher_no="PC-001",
        voucher_date=date(2026, 1, 20),
        lines=lines,
        auto_commit=True,
    )

    db.expire_all()
    result = analyze_project_cost(db, ledger.id)
    assert len(result) == 1
    assert result[0]["project"] == "审计项目2026"
    assert result[0]["total_cost"] == 8000


def test_entry_tag_vector_service_tag_text(db, ledger):
    lines = [
        VoucherEntryLine(
            account_code="1122",
            account_name="应收账款",
            summary="销售商品给D公司",
            debit_amount=30000,
            credit_amount=0,
            counterparty="D公司",
        ),
        VoucherEntryLine(
            account_code="6001",
            account_name="主营业务收入",
            summary="销售商品给D公司",
            debit_amount=0,
            credit_amount=30000,
        ),
    ]
    voucher = create_voucher(
        db,
        ledger_id=ledger.id,
        organization_id=1,
        voucher_no="VEC-001",
        voucher_date=date(2026, 1, 25),
        lines=lines,
        auto_commit=True,
    )

    service = EntryTagVectorService(db)
    entries = db.query(AccountingEntry).filter_by(voucher_id=voucher.id).order_by(AccountingEntry.entry_line_no).all()
    entry = entries[0]
    tag = entry.tags[0]
    text = service.tag_text(tag, entry)

    assert "维度" in text
    assert tag.tag_value in text
    assert entry.account_code in text
    assert str(entry.voucher_date) in text or str(entry.voucher_date).replace("-", "") in text
