# -*- coding: utf-8 -*-
"""
核心记账闭环端到端验证脚本。

业务场景：用标准会计案例验证从建账、科目、期初、凭证、损益结转到报表生成的
完整流程，并确认所有凭证均通过 voucher_service 创建，借贷保持平衡。

运行方式：
    cd backend
    python scripts/end_to_end_accounting_closure.py
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db.models import (
    AccountingEntry,
    AccountingPeriod,
    ChartOfAccounts,
    Organization,
    Voucher,
)
from app.models.ledger import Ledger
from app.models.team import Team
from app.models.user import User
from app.services.ledger_management_service import create_ledger
from app.services.voucher_service import (
    VoucherEntryLine,
    VoucherStatus,
    create_voucher,
    get_voucher_lines,
)
from app.services.period_close_service import auto_pl_transfer, reverse_pl_transfer
from app.services.financial_statements_service import compute_account_balances


def setup():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    team = Team(name="标准案例团队", type="virtual")
    db.add(team)
    db.flush()

    user = User(username="standard_case", phone="13800000002", team_id=team.id)
    db.add(user)
    db.flush()

    ledger = create_ledger(
        db,
        team_id=team.id,
        name="标准案例账簿",
        accounting_start_date=date(2026, 1, 1),
    )
    org = Organization(name="标准案例企业")
    db.add(org)
    db.flush()
    ledger.organization_id = org.id
    db.flush()

    period = db.query(AccountingPeriod).filter(AccountingPeriod.ledger_id == ledger.id).first()
    db.commit()
    return db, team, user, ledger, org, period


def _ensure_coa(db, ledger_id):
    """创建测试用科目表。"""
    accounts = [
        ("1002", "银行存款", "asset", "debit"),
        ("1122", "应收账款", "asset", "debit"),
        ("1405", "库存商品", "asset", "debit"),
        ("2202", "应付账款", "liability", "credit"),
        ("22210101", "应交税费-应交增值税-进项税额", "liability", "debit"),
        ("22210105", "应交税费-应交增值税-销项税额", "liability", "credit"),
        ("4001", "实收资本", "equity", "credit"),
        ("4103", "本年利润", "equity", "credit"),
        ("6001", "主营业务收入", "profit", "credit"),
        ("6401", "主营业务成本", "profit", "debit"),
        ("6602", "管理费用", "profit", "debit"),
    ]
    for code, name, category, direction in accounts:
        if db.query(ChartOfAccounts).filter(
            ChartOfAccounts.ledger_id == ledger_id, ChartOfAccounts.code == code
        ).first():
            continue
        db.add(
            ChartOfAccounts(
                ledger_id=ledger_id,
                code=code,
                name=name,
                category=category,
                direction=direction,
                level=1,
                is_terminal=True,
                status="active",
            )
        )
    db.flush()


def test_full_closure():
    db, team, user, ledger, org, period = setup()
    _ensure_coa(db, ledger.id)

    # 1. 收到投资款
    create_voucher(
        db,
        ledger_id=ledger.id,
        organization_id=org.id,
        voucher_no="PZ-202601-001",
        voucher_date=date(2026, 1, 5),
        summary="收到股东投资款",
        lines=[
            VoucherEntryLine(
                account_code="1002",
                account_name="银行存款",
                debit_amount=Decimal("500000.00"),
            ),
            VoucherEntryLine(
                account_code="4001",
                account_name="实收资本",
                credit_amount=Decimal("500000.00"),
            ),
        ],
        status=VoucherStatus.POSTED,
        created_by=user.id,
    )

    # 2. 采购商品
    create_voucher(
        db,
        ledger_id=ledger.id,
        organization_id=org.id,
        voucher_no="PZ-202601-002",
        voucher_date=date(2026, 1, 10),
        summary="采购库存商品",
        lines=[
            VoucherEntryLine(
                account_code="1405",
                account_name="库存商品",
                debit_amount=Decimal("200000.00"),
            ),
            VoucherEntryLine(
                account_code="22210101",
                account_name="应交税费-应交增值税-进项税额",
                debit_amount=Decimal("26000.00"),
            ),
            VoucherEntryLine(
                account_code="2202",
                account_name="应付账款",
                credit_amount=Decimal("226000.00"),
            ),
        ],
        status=VoucherStatus.POSTED,
        created_by=user.id,
    )

    # 3. 销售商品并结转成本
    create_voucher(
        db,
        ledger_id=ledger.id,
        organization_id=org.id,
        voucher_no="PZ-202601-003",
        voucher_date=date(2026, 1, 15),
        summary="销售商品",
        lines=[
            VoucherEntryLine(
                account_code="1122",
                account_name="应收账款",
                debit_amount=Decimal("339000.00"),
            ),
            VoucherEntryLine(
                account_code="6001",
                account_name="主营业务收入",
                credit_amount=Decimal("300000.00"),
            ),
            VoucherEntryLine(
                account_code="22210105",
                account_name="应交税费-应交增值税-销项税额",
                credit_amount=Decimal("39000.00"),
            ),
        ],
        status=VoucherStatus.POSTED,
        created_by=user.id,
    )
    create_voucher(
        db,
        ledger_id=ledger.id,
        organization_id=org.id,
        voucher_no="PZ-202601-004",
        voucher_date=date(2026, 1, 15),
        summary="结转销售成本",
        lines=[
            VoucherEntryLine(
                account_code="6401",
                account_name="主营业务成本",
                debit_amount=Decimal("120000.00"),
            ),
            VoucherEntryLine(
                account_code="1405",
                account_name="库存商品",
                credit_amount=Decimal("120000.00"),
            ),
        ],
        status=VoucherStatus.POSTED,
        created_by=user.id,
    )

    # 4. 支付费用
    create_voucher(
        db,
        ledger_id=ledger.id,
        organization_id=org.id,
        voucher_no="PZ-202601-005",
        voucher_date=date(2026, 1, 20),
        summary="支付管理费用",
        lines=[
            VoucherEntryLine(
                account_code="6602",
                account_name="管理费用",
                debit_amount=Decimal("30000.00"),
            ),
            VoucherEntryLine(
                account_code="1002",
                account_name="银行存款",
                credit_amount=Decimal("30000.00"),
            ),
        ],
        status=VoucherStatus.POSTED,
        created_by=user.id,
    )

    db.commit()

    # 校验所有凭证借贷平衡
    vouchers = db.query(Voucher).filter(Voucher.ledger_id == ledger.id).all()
    for v in vouchers:
        assert v.total_debit == v.total_credit, f"凭证 {v.voucher_no} 借贷不平衡"
        lines = get_voucher_lines(db, v.id)
        assert len(lines) >= 2, f"凭证 {v.voucher_no} 分录行不足"
    print(f"✅ 已创建 {len(vouchers)} 张凭证，全部借贷平衡")

    # 损益结转
    pl_result = auto_pl_transfer(db, ledger.id, period.id)
    pl_voucher_no = pl_result["voucher_no"]
    pl_voucher = db.query(Voucher).filter(Voucher.ledger_id == ledger.id, Voucher.voucher_no == pl_voucher_no).first()
    assert pl_voucher.total_debit == pl_voucher.total_credit
    print(f"✅ 损益结转凭证 {pl_voucher_no} 借贷平衡")

    # 计算科目余额
    balances = compute_account_balances(db, ledger.id, period.id)
    print(f"✅ 科目余额计算完成，共 {len(balances)} 个科目")

    # 简单资产负债表勾稽：按科目方向汇总
    # 借方方向（资产/成本）为期末借方余额；贷方方向（负债/权益/收入）为期末贷方余额。
    asset_total = Decimal("0")
    liability_equity_total = Decimal("0")
    for b in balances:
        if b["direction"] == "debit":
            asset_total += Decimal(str(b["closing_debit"])) - Decimal(str(b["closing_credit"]))
        elif b["direction"] == "credit":
            liability_equity_total += Decimal(str(b["closing_credit"])) - Decimal(str(b["closing_debit"]))

    print(f"    资产总计：{asset_total}")
    print(f"    负债+权益总计：{liability_equity_total}")
    assert asset_total == liability_equity_total, "资产负债表不平衡"
    print("✅ 资产负债表平衡")

    # 反结转验证
    reverse_pl_transfer(db, ledger.id, period.id)
    db.commit()
    vouchers_after = db.query(Voucher).filter(Voucher.ledger_id == ledger.id).all()
    print(f"✅ 反结转后账簿凭证数：{len(vouchers_after)}")

    print("\n核心记账闭环端到端验证通过。")


def main():
    test_full_closure()


if __name__ == "__main__":
    main()
