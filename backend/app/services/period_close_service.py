"""期末损益结转服务。

将本期所有 `category=profit` 科目余额结转到 `4103 本年利润`，
使资产负债表恒等式成立。

结转规则：
- 收入类（direction=credit，期末贷方有余）：借 6XXX / 贷 4103
- 成本费用类（direction=debit，期末借方有余）：借 4103 / 贷 6XXX

结转分录的凭证字为 `转-期末-{period_code}`。
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import AccountingEntry, AccountingPeriod, ChartOfAccounts
from app.services import financial_statements_service


PL_ACCOUNT_CODE = "4103"  # 本年利润
PL_TRANSFER_VOUCHER_PREFIX = "转-期末-"


def _ensure_pl_account(db: Session) -> ChartOfAccounts:
    account = db.query(ChartOfAccounts).filter(ChartOfAccounts.code == PL_ACCOUNT_CODE).first()
    if not account:
        account = ChartOfAccounts(
            code=PL_ACCOUNT_CODE,
            name="本年利润",
            parent_code=None,
            level=1,
            category="equity",
            direction="credit",
            is_terminal=True,
            status="active",
            is_system=True,
        )
        db.add(account)
        db.flush()
    return account


def auto_pl_transfer(db: Session, organization_id: int, period_id: int) -> dict:
    """对指定期间执行损益结转。"""
    period = db.get(AccountingPeriod, period_id)
    if not period:
        raise LookupError("会计期间不存在")
    if period.status == "pl_transferred":
        raise PermissionError("该期间已结转损益，请先反结转再重做")
    if period.status == "closed":
        raise PermissionError("该期间已结账，无法结转损益")

    _ensure_pl_account(db)

    rows = financial_statements_service.compute_account_balances(db, organization_id, period_id)
    voucher_no = f"{PL_TRANSFER_VOUCHER_PREFIX}{period.period_code}"

    # 删除旧的结转分录（如果有），避免重复
    db.query(AccountingEntry).filter(
        AccountingEntry.organization_id == organization_id,
        AccountingEntry.import_job_id == 0,
        AccountingEntry.voucher_no == voucher_no,
    ).delete()
    db.flush()

    voucher_date: date = period.end_date
    line_no = 0
    pl_total = Decimal("0")  # 净利润累加：贷方为 + ，借方为 -

    for row in rows:
        if row["category"] != "profit":
            continue
        period_debit = Decimal(str(row["period_debit"]))
        period_credit = Decimal(str(row["period_credit"]))
        if row["direction"] == "credit":
            # 收入类：贷方为正
            net = period_credit - period_debit
            if net == 0:
                continue
            # 借 收入科目 / 贷 4103
            line_no += 1
            db.add(
                AccountingEntry(
                    organization_id=organization_id,
                    import_job_id=0,
                    voucher_no=voucher_no,
                    voucher_date=voucher_date,
                    summary=f"结转{row['account_name']}至本年利润",
                    account_code=row["account_code"],
                    account_name=row["account_name"],
                    debit_amount=Decimal(net) if net > 0 else Decimal("0"),
                    credit_amount=Decimal(-net) if net < 0 else Decimal("0"),
                    entry_line_no=line_no,
                    normalized_text=f"结转 {row['account_name']}",
                )
            )
            line_no += 1
            db.add(
                AccountingEntry(
                    organization_id=organization_id,
                    import_job_id=0,
                    voucher_no=voucher_no,
                    voucher_date=voucher_date,
                    summary=f"结转{row['account_name']}至本年利润",
                    account_code=PL_ACCOUNT_CODE,
                    account_name="本年利润",
                    debit_amount=Decimal("0") if net > 0 else Decimal(-net),
                    credit_amount=Decimal(net) if net > 0 else Decimal("0"),
                    entry_line_no=line_no,
                    normalized_text="结转 本年利润",
                )
            )
            pl_total += net
        else:
            # 成本费用类：借方为正
            net = period_debit - period_credit
            if net == 0:
                continue
            # 借 4103 / 贷 费用科目
            line_no += 1
            db.add(
                AccountingEntry(
                    organization_id=organization_id,
                    import_job_id=0,
                    voucher_no=voucher_no,
                    voucher_date=voucher_date,
                    summary=f"结转{row['account_name']}至本年利润",
                    account_code=PL_ACCOUNT_CODE,
                    account_name="本年利润",
                    debit_amount=Decimal(net) if net > 0 else Decimal("0"),
                    credit_amount=Decimal(-net) if net < 0 else Decimal("0"),
                    entry_line_no=line_no,
                    normalized_text="结转 本年利润",
                )
            )
            line_no += 1
            db.add(
                AccountingEntry(
                    organization_id=organization_id,
                    import_job_id=0,
                    voucher_no=voucher_no,
                    voucher_date=voucher_date,
                    summary=f"结转{row['account_name']}至本年利润",
                    account_code=row["account_code"],
                    account_name=row["account_name"],
                    debit_amount=Decimal("0") if net > 0 else Decimal(-net),
                    credit_amount=Decimal(net) if net > 0 else Decimal("0"),
                    entry_line_no=line_no,
                    normalized_text=f"结转 {row['account_name']}",
                )
            )
            pl_total -= net

    period.status = "pl_transferred"
    period.updated_at = datetime.utcnow()
    db.commit()
    return {
        "period_id": period_id,
        "voucher_no": voucher_no,
        "lines": line_no,
        "net_profit": float(pl_total),
        "status": period.status,
    }


def reverse_pl_transfer(db: Session, organization_id: int, period_id: int) -> dict:
    """反结转：删除该期间的损益结转分录，并把状态恢复为 open。"""
    period = db.get(AccountingPeriod, period_id)
    if not period:
        raise LookupError("会计期间不存在")
    if period.status == "closed":
        raise PermissionError("该期间已结账，无法反结转")

    voucher_no = f"{PL_TRANSFER_VOUCHER_PREFIX}{period.period_code}"
    deleted = (
        db.query(AccountingEntry)
        .filter(
            AccountingEntry.organization_id == organization_id,
            AccountingEntry.import_job_id == 0,
            AccountingEntry.voucher_no == voucher_no,
        )
        .delete()
    )
    period.status = "open"
    period.updated_at = datetime.utcnow()
    db.commit()
    return {
        "period_id": period_id,
        "voucher_no": voucher_no,
        "deleted_lines": deleted,
        "status": period.status,
    }
