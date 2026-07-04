"""
凭证事务测试用例。

测试范围：
    1. 凭证创建事务的原子性
    2. 借贷不平衡时的事务回滚
    3. auto_commit=False 模式
    4. 凭证状态更新事务
    5. 凭证删除事务的级联效果
    6. 已过账凭证不能删除
"""
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import AccountingEntry, EntryTag, TagCategory, Voucher
from app.db.session import Base
from app.models.team import Team
from app.models.user import User
from app.services.shared.ledger_management_service import create_ledger
from app.services.doc_parsing.tag_category_service import clear_category_cache
from app.services.accounting.voucher_service import (
    VoucherBalanceError,
    VoucherEntryLine,
    create_voucher,
    delete_voucher,
    update_voucher_status,
)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    SessionClass = sessionmaker(bind=engine)
    session = SessionClass()
    yield session
    session.close()


@pytest.fixture
def ledger(db):
    clear_category_cache()
    team = Team(name="transaction_test_team", type="virtual")
    db.add(team)
    db.flush()

    user = User(username="transaction_test_user", phone="13800000005", team_id=team.id)
    db.add(user)
    db.flush()

    ledger = create_ledger(
        db,
        team_id=team.id,
        name="transaction_test_ledger",
        accounting_start_date=date(2026, 1, 1),
    )
    db.commit()
    return ledger


@pytest.fixture
def counterparty_category(db, ledger):
    category = TagCategory(
        ledger_id=ledger.id,
        code="counterparty",
        name="往来单位",
        level=1,
        value_type="text",
        is_mandatory=False,
        status="active",
    )
    db.add(category)
    db.commit()
    return category


def test_create_voucher_transaction_atomicity(db, ledger, counterparty_category):
    """
    测试凭证创建事务的原子性：
    凭证、分录、标签必须同时成功或同时失败。
    """
    lines = [
        VoucherEntryLine(
            account_code="1122",
            account_name="应收账款",
            summary="销售商品",
            debit_amount=10000,
            credit_amount=0,
            counterparty="测试客户",
            tags=[
                {
                    "category_code": "counterparty",
                    "tag_value": "测试客户",
                    "display_name": "测试客户",
                    "weight": 1.0,
                    "confidence": 0.95,
                }
            ],
        ),
        VoucherEntryLine(
            account_code="6001",
            account_name="主营业务收入",
            summary="销售商品",
            debit_amount=0,
            credit_amount=10000,
        ),
    ]

    voucher = create_voucher(
        db,
        ledger_id=ledger.id,
        organization_id=1,
        voucher_no="TEST-PZ-001",
        voucher_date=date(2026, 1, 15),
        summary="销售商品给测试客户",
        lines=lines,
    )

    assert voucher.id is not None

    entries = db.query(AccountingEntry).filter(
        AccountingEntry.voucher_id == voucher.id
    ).all()
    assert len(entries) == 2

    tags = db.query(EntryTag).filter(
        EntryTag.entry_id == entries[0].id
    ).all()
    assert len(tags) >= 1
    assert any(t.tag_value == "测试客户" for t in tags)


def test_create_voucher_rollback_on_balance_error(db, ledger):
    """
    测试借贷不平衡时的事务回滚：
    借贷不平衡时，不应创建任何数据。
    """
    lines = [
        VoucherEntryLine(
            account_code="1122",
            account_name="应收账款",
            summary="销售商品",
            debit_amount=10000,
            credit_amount=0,
        ),
        VoucherEntryLine(
            account_code="6001",
            account_name="主营业务收入",
            summary="销售商品",
            debit_amount=0,
            credit_amount=9000,
        ),
    ]

    with pytest.raises(VoucherBalanceError):
        create_voucher(
            db,
            ledger_id=ledger.id,
            organization_id=1,
            voucher_no="TEST-PZ-002",
            voucher_date=date(2026, 1, 15),
            summary="不平衡凭证",
            lines=lines,
        )

    vouchers = db.query(Voucher).filter(Voucher.voucher_no == "TEST-PZ-002").all()
    assert len(vouchers) == 0

    entries = db.query(AccountingEntry).filter(
        AccountingEntry.voucher_no == "TEST-PZ-002"
    ).all()
    assert len(entries) == 0


def test_create_voucher_with_auto_commit_false(db, ledger):
    """
    测试 auto_commit=False 模式：
    事务由调用方管理，函数不自动提交。
    """
    lines = [
        VoucherEntryLine(
            account_code="1002",
            account_name="银行存款",
            summary="收到投资款",
            debit_amount=500000,
            credit_amount=0,
        ),
        VoucherEntryLine(
            account_code="4001",
            account_name="实收资本",
            summary="收到投资款",
            debit_amount=0,
            credit_amount=500000,
        ),
    ]

    voucher = create_voucher(
        db,
        ledger_id=ledger.id,
        organization_id=1,
        voucher_no="TEST-PZ-003",
        voucher_date=date(2026, 1, 10),
        summary="收到投资款",
        lines=lines,
        auto_commit=False,
    )

    assert voucher.id is not None

    with db.begin_nested():
        count = db.query(Voucher).filter(Voucher.id == voucher.id).count()
        assert count == 1

    db.rollback()

    count = db.query(Voucher).filter(Voucher.id == voucher.id).count()
    assert count == 0


def test_update_voucher_status_transaction(db, ledger):
    """
    测试凭证状态更新事务：
    主记录和分录行状态必须同时更新。
    """
    lines = [
        VoucherEntryLine(
            account_code="1002",
            account_name="银行存款",
            summary="收款",
            debit_amount=1000,
            credit_amount=0,
        ),
        VoucherEntryLine(
            account_code="1122",
            account_name="应收账款",
            summary="收款",
            debit_amount=0,
            credit_amount=1000,
        ),
    ]

    voucher = create_voucher(
        db,
        ledger_id=ledger.id,
        organization_id=1,
        voucher_no="TEST-PZ-004",
        voucher_date=date(2026, 1, 20),
        summary="收到货款",
        lines=lines,
    )

    assert voucher.status == "draft"

    updated_voucher = update_voucher_status(
        db,
        voucher_id=voucher.id,
        status="verified",
    )

    assert updated_voucher.status == "verified"

    entries = db.query(AccountingEntry).filter(
        AccountingEntry.voucher_id == voucher.id
    ).all()
    for entry in entries:
        assert entry.review_status == "verified"
        assert entry.post_status == "verified"


def test_delete_voucher_cascades_transaction(db, ledger, counterparty_category):
    """
    测试凭证删除事务的级联效果：
    删除凭证时，分录行和标签必须同时删除。
    """
    lines = [
        VoucherEntryLine(
            account_code="1002",
            account_name="银行存款",
            summary="测试",
            debit_amount=100,
            credit_amount=0,
            tags=[
                {
                    "category_code": "counterparty",
                    "tag_value": "测试客户A",
                }
            ],
        ),
        VoucherEntryLine(
            account_code="6602",
            account_name="管理费用",
            summary="测试",
            debit_amount=0,
            credit_amount=100,
            tags=[
                {
                    "category_code": "counterparty",
                    "tag_value": "测试客户B",
                }
            ],
        ),
    ]

    voucher = create_voucher(
        db,
        ledger_id=ledger.id,
        organization_id=1,
        voucher_no="TEST-PZ-005",
        voucher_date=date(2026, 1, 25),
        summary="测试删除",
        lines=lines,
    )

    entry_ids = [e.id for e in db.query(AccountingEntry).filter(
        AccountingEntry.voucher_id == voucher.id
    ).all()]
    tag_ids = [t.id for t in db.query(EntryTag).filter(
        EntryTag.entry_id.in_(entry_ids)
    ).all()]

    assert len(entry_ids) == 2
    assert len(tag_ids) >= 1

    delete_voucher(db, voucher_id=voucher.id)

    assert db.get(Voucher, voucher.id) is None
    assert len(db.query(AccountingEntry).filter(
        AccountingEntry.id.in_(entry_ids)
    ).all()) == 0
    assert len(db.query(EntryTag).filter(
        EntryTag.id.in_(tag_ids)
    ).all()) == 0


def test_posted_voucher_cannot_be_deleted(db, ledger):
    """
    测试已过账凭证不能删除。
    """
    lines = [
        VoucherEntryLine(
            account_code="1002",
            account_name="银行存款",
            summary="测试",
            debit_amount=1000,
            credit_amount=0,
        ),
        VoucherEntryLine(
            account_code="6001",
            account_name="主营业务收入",
            summary="测试",
            debit_amount=0,
            credit_amount=1000,
        ),
    ]

    voucher = create_voucher(
        db,
        ledger_id=ledger.id,
        organization_id=1,
        voucher_no="TEST-PZ-006",
        voucher_date=date(2026, 1, 26),
        summary="测试过账",
        lines=lines,
        status="posted",
    )

    from app.services.accounting.voucher_service import VoucherStateError

    with pytest.raises(VoucherStateError):
        delete_voucher(db, voucher_id=voucher.id)

    assert db.get(Voucher, voucher.id) is not None
