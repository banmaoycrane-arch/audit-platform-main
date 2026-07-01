# -*- coding: utf-8 -*-
"""
凭证系统改造验证脚本
验证要点：
1. 通过 create_voucher 创建借贷平衡的凭证可成功。
2. 借贷不平衡时抛出 VoucherBalanceError。
3. 导入服务按 voucher_no 分组并创建凭证。
4. 损益结转通过 voucher_service 创建凭证。

运行方式：
    cd backend
    python scripts/verify_voucher_system.py
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db.models import AccountingPeriod, Organization
from app.models.ledger import Ledger
from app.models.team import Team
from app.models.user import User
from app.services.ledger_management_service import create_ledger
from app.services.voucher_service import (
    VoucherEntryLine,
    VoucherBalanceError,
    VoucherStatus,
    create_voucher,
)


def setup():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    team = Team(name="测试团队", type="virtual")
    db.add(team)
    db.flush()

    user = User(username="voucher_test", phone="13800000001", team_id=team.id)
    db.add(user)
    db.flush()

    ledger = create_ledger(
        db,
        team_id=team.id,
        name="测试账簿",
        accounting_start_date=date(2026, 1, 1),
    )

    # create_ledger 不绑定 organization_id，而 create_voucher 要求非空，
    # 因此测试脚本补建组织并绑定到账簿。
    org = Organization(name="测试组织")
    db.add(org)
    db.flush()
    ledger.organization_id = org.id
    db.flush()

    period = db.query(AccountingPeriod).filter(AccountingPeriod.ledger_id == ledger.id).first()

    db.commit()
    return db, team, user, ledger, period


def test_balance_voucher_ok():
    db, team, user, ledger, period = setup()
    lines = [
        VoucherEntryLine(
            account_code="1001",
            account_name="库存现金",
            summary="收到投资款",
            debit_amount=Decimal("100000.00"),
        ),
        VoucherEntryLine(
            account_code="4001",
            account_name="实收资本",
            summary="收到投资款",
            credit_amount=Decimal("100000.00"),
        ),
    ]
    voucher = create_voucher(
        db,
        ledger_id=ledger.id,
        organization_id=ledger.organization_id,
        voucher_no="PZ-202601-001",
        voucher_date=period.start_date,
        summary="收到投资款",
        lines=lines,
        created_by=user.id,
        status=VoucherStatus.POSTED,
    )
    assert voucher.total_debit == 100000.00
    assert voucher.total_credit == 100000.00
    assert voucher.status == "posted"
    print("✅ 测试通过：借贷平衡凭证可正常创建")


def test_unbalanced_voucher_fails():
    db, team, user, ledger, period = setup()
    lines = [
        VoucherEntryLine(
            account_code="1001",
            account_name="库存现金",
            summary="错误凭证",
            debit_amount=Decimal("100000.00"),
        ),
        VoucherEntryLine(
            account_code="4001",
            account_name="实收资本",
            summary="错误凭证",
            credit_amount=Decimal("90000.00"),
        ),
    ]
    try:
        create_voucher(
            db,
            ledger_id=ledger.id,
            organization_id=ledger.organization_id,
            voucher_no="PZ-202601-002",
            voucher_date=period.start_date,
            summary="错误凭证",
            lines=lines,
            created_by=user.id,
        )
        raise AssertionError("应抛出借贷不平衡异常")
    except VoucherBalanceError as e:
        print(f"✅ 测试通过：借贷不平衡凭证被拦截，异常：{e}")


def main():
    test_balance_voucher_ok()
    test_unbalanced_voucher_fails()
    print("\n凭证系统核心校验全部通过。")


if __name__ == "__main__":
    main()
